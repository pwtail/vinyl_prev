from django.db.models import sql
from django.db import router, connections
from django.db.models import Model as _Model, Model, ExpressionWrapper, Max, Value, IntegerField
from django.db.models.deletion import Collector
from django.db.models.functions import Coalesce
from django.db.models.query_utils import DeferredAttribute

from vinyl.futures import gen, later


class NoMetaclass(type(Model)):

    def __new__(cls, *args, **kwargs):
        return type.__new__(cls, *args, **kwargs)



class VinylModel(_Model, metaclass=NoMetaclass):


    def save(
            self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        """
        Save the current instance. Override this in a subclass if you want to
        control the saving process.

        The 'force_insert' and 'force_update' parameters can be used to insist
        that the "save" must be an SQL insert or update (or equivalent for
        non-SQL backends), respectively. Normally, they should not be set.
        """
        self._prepare_related_fields_for_save(operation_name="save")

        using = using or router.db_for_write(self.__class__, instance=self)
        if force_insert and (force_update or update_fields):
            raise ValueError("Cannot force both insert and updating in model saving.")

        deferred_fields = self.get_deferred_fields()
        if update_fields is not None:
            # If update_fields is empty, skip the save. We do also check for
            # no-op saves later on for inheritance cases. This bailout is
            # still needed for skipping signal sending.
            if not update_fields:
                return

            update_fields = frozenset(update_fields)
            field_names = set()

            for field in self._meta.concrete_fields:
                if not field.primary_key:
                    field_names.add(field.name)

                    if field.name != field.attname:
                        field_names.add(field.attname)

            non_model_fields = update_fields.difference(field_names)

            if non_model_fields:
                raise ValueError(
                    "The following fields do not exist in this model, are m2m "
                    "fields, or are non-concrete fields: %s"
                    % ", ".join(non_model_fields)
                )

        # If saving to the same database, and this model is deferred, then
        # automatically do an "update_fields" save on the loaded fields.
        elif not force_insert and deferred_fields and using == self._state.db:
            field_names = set()
            for field in self._meta.concrete_fields:
                if not field.primary_key and not hasattr(field, "through"):
                    field_names.add(field.attname)
            loaded_fields = field_names.difference(deferred_fields)
            if loaded_fields:
                update_fields = frozenset(loaded_fields)

        return self.save_base(
            using=using,
            force_insert=force_insert,
            force_update=force_update,
            update_fields=update_fields,
        )


    @gen
    def save_base(self, raw=False, force_insert=False,
                  force_update=False, using=None, update_fields=None):
        """
        Handle the parts of saving which should be done only once per save,
        yet need to be done in raw saves, too. This includes some sanity
        checks and signal sending.

        The 'raw' argument is telling save_base not to save any parent
        models and not to do any changes to the values before save. This
        is used by fixture loading.
        """
        assert not (force_insert and (force_update or update_fields))
        assert update_fields is None or update_fields
        cls = origin = self.__class__
        # Skip proxies, but keep the origin as the proxy model.
        if cls._meta.proxy:
            cls = cls._meta.concrete_model
        meta = cls._meta

        parent_inserted = False
        if not raw:
            parent_inserted = yield from self._save_parents(cls, using, update_fields)
        updated = yield from self._save_table(
            raw, cls, force_insert or parent_inserted,
            force_update, using, update_fields,
                      )
        # Store the database on which the object was saved
        self._state.db = using
        # Once saved, this is no longer a to-be-added instance.
        self._state.adding = False

    save_base.alters_data = True

    def _save_parents(self, cls, using, update_fields):
        """Save all the parents of cls using values from self."""
        meta = cls._meta
        inserted = False
        for parent, field in meta.parents.items():
            # Make sure the link fields are synced between parent and self.
            if (field and getattr(self, parent._meta.pk.attname) is None and
                    getattr(self, field.attname) is not None):
                setattr(self, parent._meta.pk.attname, getattr(self, field.attname))
            parent_inserted = yield from self._save_parents(cls=parent, using=using, update_fields=update_fields)
            updated = yield from self._save_table(
                cls=parent, using=using, update_fields=update_fields,
                force_insert=parent_inserted,
            )
            if not updated:
                inserted = True
            # Set the parent's PK value to self.
            if field:
                setattr(self, field.attname, self._get_pk_val(parent._meta))
                # Since we didn't have an instance of the parent handy set
                # attname directly, bypassing the descriptor. Invalidate
                # the related object cache, in case it's been accidentally
                # populated. A fresh instance will be re-built from the
                # database if necessary.
                if field.is_cached(self):
                    field.delete_cached_value(self)
        return inserted

    def _save_table(self, raw=False, cls=None, force_insert=False,
                    force_update=False, using=None, update_fields=None):
        """
        Do the heavy-lifting involved in saving. Update or insert the data
        for a single table.
        """
        meta = cls._meta
        non_pks = [f for f in meta.local_concrete_fields if not f.primary_key]

        if update_fields:
            non_pks = [f for f in non_pks
                       if f.name in update_fields or f.attname in update_fields]

        pk_val = self._get_pk_val(meta)
        if pk_val is None:
            pk_val = meta.pk.get_pk_value_on_save(self)
            setattr(self, meta.pk.attname, pk_val)
        pk_set = pk_val is not None
        if not pk_set and (force_update or update_fields):
            raise ValueError("Cannot force an update in save() with no primary key.")
        updated = False
        # Skip an UPDATE when adding an instance and primary key has a default.
        if (
                not raw and
                not force_insert and
                self._state.adding and
                meta.pk.default and
                meta.pk.default is not NOT_PROVIDED
        ):
            force_insert = True
        # If possible, try an UPDATE. If that doesn't update anything, do an INSERT.
        if pk_set and not force_insert:
            base_qs = cls._base_manager.using(using)
            values = [(f, None, (getattr(self, f.attname) if raw else f.pre_save(self, False)))
                      for f in non_pks]
            forced_update = update_fields or force_update
            updated = yield from self._do_update(base_qs, using, pk_val, values, update_fields,
                                                 forced_update)
            if force_update and not updated:
                raise DatabaseError("Forced update did not affect any rows.")
            if update_fields and not updated:
                raise DatabaseError("Save with update_fields did not affect any rows.")
        if not updated:
            if meta.order_with_respect_to:
                # If this is a model with an order_with_respect_to
                # autopopulate the _order field
                field = meta.order_with_respect_to
                filter_args = field.get_filter_kwargs_for_object(self)
                self._order = cls._base_manager.using(using).filter(**filter_args).aggregate(
                    _order__max=Coalesce(
                        ExpressionWrapper(Max('_order') + Value(1), output_field=IntegerField()),
                        Value(0),
                    ),
                )['_order__max']
            fields = meta.local_concrete_fields
            if not pk_set:
                fields = [f for f in fields if f is not meta.auto_field]

            returning_fields = meta.db_returning_fields
            results = yield self._do_insert(cls._base_manager, using, fields, returning_fields, raw)

            if results:
                for value, field in zip(results[0], returning_fields):
                    setattr(self, field.attname, value)
        return updated

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Try to update the model. Return True if the model was updated (if an
        update query was done and a matching row was found in the DB).
        """
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            # We can end up here when saving a model in inheritance chain where
            # update_fields doesn't target any field in current model. In that
            # case we just say the update succeeded. Another case ending up here
            # is a model with just PK - in that case check that the PK still
            # exists.
            return update_fields is not None or (yield filtered.exists())
        if self._meta.select_on_save and not forced_update:
            return (
                    (yield filtered.exists()) and
                    # It may happen that the object is deleted from the DB right after
                    # this check, causing the subsequent UPDATE to return zero matching
                    # rows. The same result can occur in some rare cases when the
                    # database returns zero despite the UPDATE being executed
                    # successfully (a row is matched and updated). In order to
                    # distinguish these two cases, the object's existence in the
                    # database is again checked for if the UPDATE query returns 0.
                    (
                            (yield filtered._update(values) > 0) or (yield filtered.exists())
                    )
            )
        return (yield filtered._update(values)) > 0


class VModel:



    def _insert_table(
        self,
        raw=False,
        using=None,
        update_fields=None,
    ):
        """
        Do the heavy-lifting involved in saving. Update or insert the data
        for a single table.
        """
        cls = self.__class__
        meta = cls._meta

        pk_val = getattr(self, meta.pk.attname)
        if pk_val is None:
            pk_val = meta.pk.get_pk_value_on_save(self)
            setattr(self, meta.pk.attname, pk_val)
        pk_set = pk_val is not None

        fields = meta.local_concrete_fields
        if not pk_set:
            fields = [f for f in fields if f is not meta.auto_field]

        returning_fields = meta.db_returning_fields
        results = meta.model.vinyl._insert(
            [self],
            fields=fields,
            returning_fields=returning_fields,
            using=using,
            raw=raw,
        )

        @later
        def insert(results=results):
            if results:
                for value, field in zip(results[0], returning_fields):
                    setattr(self, field.attname, value)

        return insert()

    insert = _insert_table

    # def insert(self, using=None):
    #     # using = using or router.db_for_write(self.model, instance=obj)
    #     using = 'vinyl_default'
    #     meta = self._meta
    #     query = sql.InsertQuery(meta.model)
    #     fields = meta.local_concrete_fields
    #     returning_fields = meta.db_returning_fields
    #     fields = [f for f in fields if f is not meta.auto_field]
    #     query.insert_values(fields, [self])
    #     rows = query.get_compiler(using=using).execute_sql(returning_fields)
    #
    #     @later
    #     def insert(rows=rows):
    #         if rows:
    #             for value, field in zip(rows[0], returning_fields):
    #                 setattr(self, field.attname, value)
    #
    #     return insert()


def get_vinyl_model(model_cls):
    name = model_cls.__name__


def make_model_class(cls):
    bases = []

    for base in cls.__bases__:
        if base is not Model:
            bases.append(base)
        else:
            bases.append(VinylModel)
    ns = {
        '_meta': cls._meta,
    }
    for key, val in cls.__dict__.items():
        if isinstance(val, DeferredAttribute):
            ns[key] = val
    new_cls = type(cls.__name__, tuple(bases), ns)
    return new_cls
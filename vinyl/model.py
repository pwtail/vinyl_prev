from django.db.models import DEFERRED
from vinyl.futures import gen, later
from django.db import models


class ModelMixin:

    def _get_pk_val(self, meta=None):
        meta = meta or self._meta
        return getattr(self, meta.pk.attname)

    def _set_pk_val(self, value):
        for parent_link in self._meta.parents.values():
            if parent_link and parent_link != self._meta.pk:
                setattr(self, parent_link.target_field.attname, value)
        return setattr(self, self._meta.pk.attname, value)

    pk = property(_get_pk_val, _set_pk_val)

    @classmethod
    def from_db(cls, db, field_names, values):
        if len(values) != len(cls._meta.concrete_fields):
            values_iter = iter(values)
            values = [
                next(values_iter) if f.attname in field_names else DEFERRED
                for f in cls._meta.concrete_fields
            ]
        new = cls(*values)
        new._state.adding = False
        new._state.db = db
        return new


class VinylMeta:
    def __get__(self, instance, owner):
        return owner._model._meta


class VinylModel(ModelMixin):
    _model = None

    #?
    _meta = VinylMeta()

    #TODO __init__?
    def __new__(cls, *args, **kwargs):
        ob = cls._model(*args, **kwargs)
        ob.__class__ = cls
        return ob

    @property
    def insert(self):
        cls = self.__class__
        if cls._meta.parents:
            return self.insert_with_parents
        return self._insert

    def _insert(
        self,
        cls=None,
        using=None,
    ):
        if cls is None:
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
        from vinyl.manager import _VinylManager
        manager = _VinylManager()
        #FIXME
        manager.model = get_vinyl_model(meta.model)
        results = manager._insert(
            [self],
            fields=fields,
            returning_fields=returning_fields,
            using=using,
        )

        @later
        def insert(results=results):
            if results:
                for value, field in zip(results[0], returning_fields):
                    setattr(self, field.attname, value)

        return insert()

    def _insert_with_parents(self, cls=None, using=None):
        if cls is None:
            cls = self.__class__
        meta = cls._meta

        for parent, field in meta.parents.items():
            # Make sure the link fields are synced between parent and self.
            if (
                field
                and getattr(self, parent._meta.pk.attname) is None
                and getattr(self, field.attname) is not None
            ):
                setattr(self, parent._meta.pk.attname, getattr(self, field.attname))
            yield from self._insert_with_parents(cls=parent, using=using)
            if field:
                setattr(self, field.attname, self._get_pk_val(parent._meta))

        yield self._insert(cls=cls, using=using)

    insert_with_parents = gen(_insert_with_parents)

    @property
    def delete(self):
        cls = self.__class__
        if cls._meta.parents:
            return self.delete_with_parents
        return self._delete

    def _delete(self, cls=None, using=None):
        if cls is None:
            cls = self.__class__
        from vinyl.manager import _VinylManager
        manager = _VinylManager()
        manager.model = get_vinyl_model(cls._meta.model)
        num_rows = manager._delete(
            [self],
            using=using,
        )
        return num_rows

    def _delete_with_parents(self, cls=None, using=None):
        if cls is None:
            cls = self.__class__
        num_rows = yield self._delete(cls=cls, using=using)

        for parent, field in cls._meta.parents.items():
            count = yield from self._delete_with_parents(cls=parent, using=using)
            num_rows += count

        return num_rows

    delete_with_parents = gen(_delete_with_parents)


    def _update(self, cls=None, using=None, **kwargs):
        cls = self.__class__
        meta = cls._meta

        def values():
            for field in meta.local_concrete_fields:
                if field.primary_key:
                    continue
                if field.name in kwargs:
                    yield field, None, kwargs[field.name]

        values = tuple(values())

        pk_val = self._get_pk_val(meta)
        base_qs = meta.model.vinyl.using(using)
        cursor = base_qs.filter(pk=pk_val)._update(values)

        # TODO returning

        @later
        def update(cursor=cursor):
            count = cursor.rowcount if cursor else 0
            if count == 1:
                for field, _, value in values:
                    setattr(self, field.attname, value)
                return True
            return False

        return update()


vinyl_models = {}

def get_vinyl_model(model_cls):
    if model := vinyl_models.get(model_cls):
        return model

    name = model_cls.__name__

    model = type(
        name, (VinylModel,), {'_model': model_cls}
    )
    vinyl_models[model_cls] = model
    return model
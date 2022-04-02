from django.db.models import sql, DEFERRED
from django.db import router, connections
from django.db.models import Model as _Model, Model, ExpressionWrapper, Max, Value, IntegerField
from django.db.models.deletion import Collector
from django.db.models.functions import Coalesce
from django.db.models.query_utils import DeferredAttribute
from django.db.models.sql.constants import CURSOR

from vinyl.futures import gen, later


class NoMetaclass(type(Model)):

    def __new__(cls, *args, **kwargs):
        return type.__new__(cls, *args, **kwargs)


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



class VModel(ModelMixin):



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

    def delete(self, using=None):
        cls = self.__class__
        meta = cls._meta
        model = meta.model

        #TODO
        # results = meta.model.vinyl._delete(
        #     [self],
        #     using=using,
        # )

        query = sql.DeleteQuery(model)
        query.clear_where()
        query.add_filter(
            meta.pk.attname,
            self.pk,
        )
        cursor = query.get_compiler(using).execute_sql(CURSOR)

        @later
        def delete(cursor=cursor):
            if cursor:
                return cursor.rowcount
            return 0

        return delete()




def get_vinyl_model(model_cls):
    app_label = model_cls._meta.app_label
    name = model_cls.__name__
    from importlib import import_module
    vmodels = import_module(f'{app_label}.vmodels')
    if hasattr(vmodels, name):
        return getattr(vmodels, name)
    assert 0
    # getatt


# def make_model_class(cls):
#     bases = []
#
#     for base in cls.__bases__:
#         if base is not Model:
#             bases.append(base)
#         else:
#             bases.append(VinylModel)
#     ns = {
#         '_meta': cls._meta,
#     }
#     for key, val in cls.__dict__.items():
#         if isinstance(val, DeferredAttribute):
#             ns[key] = val
#     new_cls = type(cls.__name__, tuple(bases), ns)
#     return new_cls
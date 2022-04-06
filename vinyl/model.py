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

    # @staticmethod
    # def _get_parents_tree(cls):
    #     meta = cls._meta
    #     result = {}
    #     for parent, field in meta.parents.items():
    #         result[parent] = VModel._get_parents_tree(parent)
    #     return result

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
        results = meta.model.vinyl._insert(
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
        model = cls._meta.model
        num_rows = model.vinyl._delete(
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
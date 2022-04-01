import operator
from functools import cached_property

from django.db import DatabaseError, router
from django.db.models import Manager as DjangoManager, NOT_PROVIDED, ExpressionWrapper, Max, Value
from django.db.models import QuerySet
from django.db.models.base import ModelBase
from django.db.models.functions import Coalesce
from django.db.models.query import get_related_populators
from django.forms import IntegerField

from vinyl import iterables
from vinyl.model import make_model_class
from vinyl.futures import gen, is_async, later

from django.db.models import Model as _Model


class VinylQuerySet(QuerySet):

    @property
    def db(self):
        db = super().db
        return f'vinyl_{db}'

    def __init__(self, model=None, query=None, using=None, hints=None):
        #FIXME
        model = make_model_class(model)
        super().__init__(model=model, query=query, using=using, hints=hints)

    def __iter__(self):
        self._fetch_all_()
        return iter(self._result_cache)

    def get_vinyl_iterable_class(self):
        return getattr(iterables, self._iterable_class.__name__)

    def _fetch_all_(self):
        iterable_class = self.get_vinyl_iterable_class()
        results = iterable_class(self).get_objects()

        if self._prefetch_related_lookups and not self._prefetch_done:
            prefetch = self._prefetch_related_objects()
        else:
            prefetch = None

        @later
        def _fetch_all_(result_cache=results, prefetch=prefetch):
            self._result_cache = result_cache
            return result_cache

        return _fetch_all_()


    def _fetch_all(self):
        "Do nothing."

    def __await__(self):
        return self._fetch_all_().__await__()


class VinylManager(DjangoManager.from_queryset(VinylQuerySet)):
    pass
    # def bulk_insert(self, objs):
    #     using = self.db
    #     query = sql.InsertQuery(
    #         self.model,
    #         on_conflict=on_conflict,
    #         update_fields=update_fields,
    #         unique_fields=unique_fields,
    #     )
    #     query.insert_values(fields, objs, raw=raw)
    #     return query.get_compiler(using=using).execute_sql(returning_fields)

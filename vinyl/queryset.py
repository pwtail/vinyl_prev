import operator
from functools import cached_property

from django.db import DatabaseError, router
from django.db.models import Manager as DjangoManager, NOT_PROVIDED, ExpressionWrapper, Max, Value, sql
from django.db.models import QuerySet
from django.db.models.base import ModelBase
from django.db.models.functions import Coalesce
from django.db.models.query import get_related_populators
from django.db.models.sql.constants import CURSOR
from django.forms import IntegerField

from vinyl import iterables

from vinyl.futures import gen, is_async, later

from django.db.models import Model as _Model


class VinylQuerySet(QuerySet):

    @property
    def db(self):
        db = super().db
        return f'vinyl_{db}'

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

    def _delete(self, objs, using=None):
        if using is None:
            using = self.db
        meta = self.model._meta
        pk_list = [
            getattr(obj, meta.pk.attname) for obj in objs
        ]
        query = sql.DeleteQuery(self.model)
        # query.clear_where()
        query.add_filter(
            f"{meta.pk.attname}__in",
            pk_list,
        )
        cursor = query.get_compiler(using).execute_sql(CURSOR)

        @later
        def delete(cursor=cursor):
            if cursor:
                return cursor.rowcount
            return 0

        return delete()

    _delete.queryset_only = False



class VinylManager(DjangoManager.from_queryset(VinylQuerySet)):
    pass

from django.db import connections, NotSupportedError
from django.db.models import sql
from django.db.models import QuerySet
from django.db.models.sql.constants import CURSOR
from django.db.models.query import MAX_GET_RESULTS

from vinyl import iterables

from vinyl.futures import later, is_async
from vinyl.prefetch import prefetch_related_objects
from vinyl.query import VinylQuery


class VinylQuerySet(QuerySet):

    def __init__(self, model=None, query=None, using=None, hints=None):
        query = query or VinylQuery(model)
        super().__init__(model=model, query=query, using=using, hints=hints)

    @property
    def db(self):
        db = super().db
        if db.startswith('vinyl_'):
            return db
        return f'vinyl_{db}'

    def __iter__(self):
        if not is_async():
            self._fetch_all_()
        return iter(self._result_cache)

    def get_vinyl_iterable_class(self):
        return getattr(iterables, self._iterable_class.__name__)

    def _fetch_all_(self):
        if not (results := self._result_cache):
            iterable_class = self.get_vinyl_iterable_class()
            results = iterable_class(self).get_objects()

        @later
        def prefetch(result_cache=results):
            self._result_cache = result_cache
            if self._prefetch_related_lookups and not self._prefetch_done:
                return self._prefetch_related_objects()

        return prefetch()

    def _prefetch_related_objects(self):
        # This method can only be called once the result cache has been filled.
        result = prefetch_related_objects(self._result_cache, *self._prefetch_related_lookups)

        @later
        def prefetch(_=result):
            self._prefetch_done = True

        return prefetch()

    def _fetch_all(self):
        "Do nothing."

    def __await__(self):
        return self._await().__await__()

    async def _await(self):
        await self._fetch_all_()
        return self._result_cache

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

    def get(self, *args, **kwargs):
        """
        Perform the query and return a single object matching the given
        keyword arguments.
        """
        if self.query.combinator and (args or kwargs):
            raise NotSupportedError(
                "Calling QuerySet.get(...) with filters after %s() is not "
                "supported." % self.query.combinator
            )
        clone = self._chain() if self.query.combinator else self.filter(*args, **kwargs)
        if self.query.can_filter() and not self.query.distinct_fields:
            clone = clone.order_by()
        limit = None
        if (
            not clone.query.select_for_update
            or connections[clone.db].features.supports_select_for_update_with_limit
        ):
            limit = MAX_GET_RESULTS
            clone.query.set_limits(high=limit)

        @later
        def get(_=clone):
            if not is_async():
                clone._fetch_all_()
            return clone._get(limit=limit)

        return get()

    def _get(self, limit=None):
        num = len(self._result_cache)
        if num == 1:
            return self._result_cache[0]
        if not num:
            raise self.model.DoesNotExist(
                "%s matching query does not exist." % self.model._meta.object_name
            )
        raise self.model.MultipleObjectsReturned(
            "get() returned more than one %s -- it returned %s!"
            % (
                self.model._meta.object_name,
                num if not limit or num < limit else "more than %s" % (limit - 1),
            )
        )

    def first(self):
        qs = (self if self.ordered else self.order_by("pk"))[:1]

        @later
        def first(qs=qs):
            if not is_async():
                qs._fetch_all_()
            for obj in qs:
                return obj

        return first()

    def last(self):
        qs = (self.reverse() if self.ordered else self.order_by("-pk"))[:1]

        @later
        def last(qs=qs):
            if not is_async():
                qs._fetch_all_()
            for obj in qs:
                return obj

        return last()


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
    @classmethod
    def clone(cls, qs):
        c = cls(
            model=qs.model,
            query=qs.query.chain(klass=VinylQuery),
            using=qs._db,
            hints=qs._hints,
        )
        c._sticky_filter = qs._sticky_filter
        c._for_write = qs._for_write
        c._prefetch_related_lookups = qs._prefetch_related_lookups[:]
        c._known_related_objects = qs._known_related_objects
        c._iterable_class = qs._iterable_class
        c._fields = qs._fields
        return c

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
        assert not is_async()
        return self._fetch_all_()
        # return iter(self._result_cache)

    def get_vinyl_iterable_class(self):
        return getattr(iterables, self._iterable_class.__name__)

    #TODO drop _result_cache
    #TODO evaluate
    def _fetch_all_(self):
        # if not (results := self._result_cache):
        iterable_class = self.get_vinyl_iterable_class()
        results = iterable_class(self).get_objects()

        @later
        def prefetch(results=results):
            return prefetch_related_objects(results, *self._prefetch_related_lookups)
        # prefetch = later(prefetch_related_objects)  #TODO

        return prefetch()


    def _fetch_all(self):
        "Do nothing."

    def __await__(self):
        return self._await().__await__()

    _await = _fetch_all_

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
        def get(results=clone._fetch_all_()):
            return clone._get(results, limit=limit)

        return get()

    def _get(self, results, limit=None):
        num = len(results)
        if num == 1:
            return results[0]
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
        def first(qs=qs._fetch_all_()):
            for obj in qs:
                return obj

        return first()

    def last(self):
        qs = (self.reverse() if self.ordered else self.order_by("-pk"))[:1]

        @later
        def last(qs=qs._fetch_all_()):
            for obj in qs:
                return obj

        return last()

    def prefetch(self, *lookups):
        return self.prefetch_related(*lookups)


    def get_or_none(self):
        if not is_async():
            try:
                return self.get()
            except self.model.DoesNotExist:
                return None

        async def get_or_none():
            try:
                return await self.get()
            except self.model.DoesNotExist:
                return None

        return get_or_none()
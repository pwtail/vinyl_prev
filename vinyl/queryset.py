import operator
from functools import cached_property

from django.db import DatabaseError, router
from django.db.models import Manager as DjangoManager, NOT_PROVIDED, ExpressionWrapper, Max, Value, Count, sql
from django.db.models import QuerySet
from django.db.models.base import ModelBase
from django.db.models.functions import Coalesce
from django.db.models.query import get_related_populators
from django.db.models.sql.constants import CURSOR, SINGLE
from django.forms import IntegerField
from django.db.models.query import MAX_GET_RESULTS

from vinyl import iterables

from vinyl.futures import gen, is_async, later

from django.db.models import Model as _Model


class VinylQuery(sql.Query):

    def get_count(self, using):
        """
        Perform a COUNT() query using the current filter constraints.
        """
        obj = self.clone()
        obj.add_annotation(Count("*"), alias="__count", is_summary=True)
        result = obj.get_aggregation(using, ["__count"])

        @later
        def get_count(result=result):
            number = result["__count"]
            if number is None:
                number = 0
            return number

        return get_count()

    def get_aggregation(self, using, added_aggregate_names):
        """
        Return the dictionary with the values of the existing aggregations.
        """
        if not self.annotation_select:
            return {}
        existing_annotations = [
            annotation
            for alias, annotation in self.annotations.items()
            if alias not in added_aggregate_names
        ]
        # Decide if we need to use a subquery.
        #
        # Existing annotations would cause incorrect results as get_aggregation()
        # must produce just one result and thus must not use GROUP BY. But we
        # aren't smart enough to remove the existing annotations from the
        # query, so those would force us to use GROUP BY.
        #
        # If the query has limit or distinct, or uses set operations, then
        # those operations must be done in a subquery so that the query
        # aggregates on the limit and/or distinct results instead of applying
        # the distinct and limit after the aggregation.
        if (
            isinstance(self.group_by, tuple)
            or self.is_sliced
            or existing_annotations
            or self.distinct
            or self.combinator
        ):
            from django.db.models.sql.subqueries import AggregateQuery

            inner_query = self.clone()
            inner_query.subquery = True
            outer_query = AggregateQuery(self.model, inner_query)
            inner_query.select_for_update = False
            inner_query.select_related = False
            inner_query.set_annotation_mask(self.annotation_select)
            # Queries with distinct_fields need ordering and when a limit is
            # applied we must take the slice from the ordered query. Otherwise
            # no need for ordering.
            inner_query.clear_ordering(force=False)
            if not inner_query.distinct:
                # If the inner query uses default select and it has some
                # aggregate annotations, then we must make sure the inner
                # query is grouped by the main model's primary key. However,
                # clearing the select clause can alter results if distinct is
                # used.
                has_existing_aggregate_annotations = any(
                    annotation
                    for annotation in existing_annotations
                    if getattr(annotation, "contains_aggregate", True)
                )
                if inner_query.default_cols and has_existing_aggregate_annotations:
                    inner_query.group_by = (
                        self.model._meta.pk.get_col(inner_query.get_initial_alias()),
                    )
                inner_query.default_cols = False

            relabels = {t: "subquery" for t in inner_query.alias_map}
            relabels[None] = "subquery"
            # Remove any aggregates marked for reduction from the subquery
            # and move them to the outer AggregateQuery.
            col_cnt = 0
            for alias, expression in list(inner_query.annotation_select.items()):
                annotation_select_mask = inner_query.annotation_select_mask
                if expression.is_summary:
                    expression, col_cnt = inner_query.rewrite_cols(expression, col_cnt)
                    outer_query.annotations[alias] = expression.relabeled_clone(
                        relabels
                    )
                    del inner_query.annotations[alias]
                    annotation_select_mask.remove(alias)
                # Make sure the annotation_select wont use cached results.
                inner_query.set_annotation_mask(inner_query.annotation_select_mask)
            if (
                inner_query.select == ()
                and not inner_query.default_cols
                and not inner_query.annotation_select_mask
            ):
                # In case of Model.objects[0:3].count(), there would be no
                # field selected in the inner query, yet we must use a subquery.
                # So, make sure at least one field is selected.
                inner_query.select = (
                    self.model._meta.pk.get_col(inner_query.get_initial_alias()),
                )
        else:
            outer_query = self
            self.select = ()
            self.default_cols = False
            self.extra = {}

        empty_set_result = [
            expression.empty_result_set_value
            for expression in outer_query.annotation_select.values()
        ]
        elide_empty = not any(result is NotImplemented for result in empty_set_result)
        outer_query.clear_ordering(force=True)
        outer_query.clear_limits()
        outer_query.select_for_update = False
        outer_query.select_related = False
        compiler = outer_query.get_compiler(using, elide_empty=elide_empty)
        result = compiler.execute_sql(SINGLE)

        @later
        def get_aggregation(result=result):
            if result is None:
                result = empty_set_result

            converters = compiler.get_converters(outer_query.annotation_select.values())
            result = next(compiler.apply_converters((result,), converters))

            return dict(zip(outer_query.annotation_select, result))

        return get_aggregation()


class VinylQuerySet(QuerySet):

    def __init__(self, model=None, query=None, using=None, hints=None):
        query = query or VinylQuery(model)
        super().__init__(model=model, query=query, using=using, hints=hints)

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
            return clone._get()

        return get()

    def _get(self):
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


class VinylManager(DjangoManager.from_queryset(VinylQuerySet)):
    pass

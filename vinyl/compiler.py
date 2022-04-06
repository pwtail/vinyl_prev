import typing

from django.core.exceptions import EmptyResultSet
from django.db import connection, connections
from django.db.models.sql.compiler import SQLCompiler as DjangoSQLCompiler
from django.db.models.sql.compiler import SQLUpdateCompiler as DjangoSQLUpdateCompiler
from django.db.models.sql import compiler as _compiler
from django.db.models.sql.constants import SINGLE, MULTI, NO_RESULTS, CURSOR

from vinyl.futures import later, gen, sequence

from django.db.models.sql.compiler import *


class ExecuteMixin:

    @property
    def execute_sql(self):
        connection = connections[self.using]
        return connection.cursor(self._execute_sql)

    def _execute_sql(self, result_type=MULTI, *, cursor):
        result_type = result_type or NO_RESULTS
        try:
            sql, params = self.as_sql()
            if not sql:
                raise EmptyResultSet
        except EmptyResultSet:
            if result_type == MULTI:
                return iter([])
            else:
                return
        execute = cursor.execute(sql, params)
        fetchone = fetchall = None
        if result_type == SINGLE:
            fetchone = cursor.fetchone()
        elif result_type == MULTI:
            fetchall = cursor.fetchall()

        @later
        def execute_sql(_=execute, val=fetchone, rows=fetchall):
            if result_type == SINGLE:
                if val:
                    return val[0:self.col_count]
                return val
            elif result_type == MULTI:
                return rows
            elif result_type == NO_RESULTS:
                return None
            elif result_type == CURSOR:
                return RetCursor(cursor.rowcount, getattr(cursor, 'lastrowid', None))

        return execute_sql()


class SQLCompiler(ExecuteMixin, _compiler.SQLCompiler):

    def convert_rows(self, rows, tuple_expected=False):
        "Apply converters."
        fields = [s[0] for s in self.select[0 : self.col_count]]
        converters = self.get_converters(fields)
        if converters:
            rows = self.apply_converters(rows, converters)
            if tuple_expected:
                rows = map(tuple, rows)
        return rows

    def has_results(self):
        """
        Backends (e.g. NoSQL) can override this in order to use optimized
        versions of "query has any results."
        """
        result = self.execute_sql(SINGLE)

        @later
        def ret(result=result):
            return bool(result)
        return ret()



class RetCursor(typing.NamedTuple):
    """
    An object to return when result_type is CURSOR
    """
    rowcount: int
    lastrowid: object

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def close(self):
        pass


class SQLInsertCompiler(ExecuteMixin, _compiler.SQLInsertCompiler):

    @property
    def execute_sql(self):
        connection = connections[self.using]
        return connection.cursor(self._execute_sql)

    #FIXME self.connection

    def _execute_sql(self, returning_fields=None, *, cursor):
        assert not (
            returning_fields
            and len(self.query.objs) != 1
            and not self.connection.features.can_return_rows_from_bulk_insert
        )
        opts = self.query.get_meta()
        self.returning_fields = returning_fields
        [(sql, params)] = self.as_sql()
        execute = cursor.execute(sql, params)

        if not self.returning_fields:
            @later
            def empty(execute=execute):
                return []
            return empty()
        if (
            self.connection.features.can_return_rows_from_bulk_insert
            and len(self.query.objs) > 1
        ):
            @later
            def get_rows(execute=execute):
                return self.connection.ops.fetch_returned_insert_rows(cursor)
        elif self.connection.features.can_return_columns_from_insert:
            assert len(self.query.objs) == 1
            row = self.connection.ops.fetch_returned_insert_columns(
                cursor,
                self.returning_params,
            )
            @later
            def get_rows(execute=execute, row=row):
                return [row]
        else:
            last_insert_id = self.connection.ops.last_insert_id(
                cursor,
                opts.db_table,
                opts.pk.column,
            )
            @later
            def get_rows(execute=execute, last_insert_id=last_insert_id):
                return [(last_insert_id,)]

        rows = get_rows()
        return self._convert_rows(rows=rows)

    @later
    def _convert_rows(self, *, rows):
        opts = self.query.get_meta()
        cols = [opts.pk.get_col(opts.db_table)]
        converters = self.get_converters(cols)
        if converters:
            rows = list(self.apply_converters(rows, converters))
        return rows


class SQLDeleteCompiler(ExecuteMixin, _compiler.SQLDeleteCompiler):
    pass


class SQLUpdateCompiler(ExecuteMixin, _compiler.SQLUpdateCompiler):
    pass

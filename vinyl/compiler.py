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
                return RetCursor(cursor.rowcount, cursor.lastrowid)

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
    #
    # def apply_converters_(self, rows):
    #     fields = [s[0] for s in self.select[0:self.col_count]]
    #     converters = self.get_converters(fields)
    #     if not converters:
    #         return rows
    #     connection = self.connection
    #     converters = list(converters.items())
    #     rows = [list(row) for row in rows]
    #     for row in rows:
    #         for pos, (convs, expression) in converters:
    #             value = row[pos]
    #             for converter in convs:
    #                 value = converter(value, expression, connection)
    #             row[pos] = value
    #     return rows


class SQLUpdateCompiler(ExecuteMixin, _compiler.SQLUpdateCompiler):
    #FIXME
    @gen
    def execute_sql(self, result_type):
        """
        Execute the specified update. Return the number of rows affected by
        the primary update query. The "primary update query" is the first
        non-empty query that is executed. Row counts for any subsequent,
        related queries are not available.
        """
        cursor = yield super().execute_sql(result_type)
        try:
            rows = cursor.rowcount if cursor else 0
            is_empty = cursor is None
        finally:
            if cursor:
                cursor.close()
        for query in self.query.get_related_updates():
            aux_rows = yield query.get_compiler(self.using).execute_sql(result_type)
            if is_empty and aux_rows:
                rows = aux_rows
                is_empty = False
        return rows


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

    def _execute_sql(self, *, cursor):
        "Always returns pk's of inserted objects"
        opts = self.query.get_meta()

        [(sql, params)] = self.as_sql()
        _ = cursor.execute(sql, params)

        last_insert_id = self.connection.ops.last_insert_id(
            cursor,
            opts.db_table,
            opts.pk.column,
        ),

        @later
        def _execute_sql(_=_, last_insert_id=last_insert_id):
            assert len(self.query.objs) == 1
            rows = [
                (last_insert_id,)
            ]
            cols = [opts.pk.get_col(opts.db_table)]
            converters = self.get_converters(cols)
            if converters:
                rows = list(self.apply_converters(rows, converters))
            return rows

        return _execute_sql()
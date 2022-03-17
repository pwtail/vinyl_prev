import typing

from django.core.exceptions import EmptyResultSet
from django.db import connection, connections
from django.db.models.sql.compiler import SQLCompiler as DjangoSQLCompiler
from django.db.models.sql.compiler import SQLUpdateCompiler as DjangoSQLUpdateCompiler
from django.db.models.sql.constants import SINGLE, MULTI, NO_RESULTS, CURSOR

from vinyl.futures import later, gen

from django.db.models.sql.compiler import *


class SQLCompiler(DjangoSQLCompiler):

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

    def apply_converters_(self, rows):
        fields = [s[0] for s in self.select[0:self.col_count]]
        converters = self.get_converters(fields)
        if not converters:
            return rows
        connection = self.connection
        converters = list(converters.items())
        rows = [list(row) for row in rows]
        for row in rows:
            for pos, (convs, expression) in converters:
                value = row[pos]
                for converter in convs:
                    value = converter(value, expression, connection)
                row[pos] = value
        return rows

    @property
    def execute_sql(self):
        connection = connections[self.using]
        return connection.cursor(self._execute_sql)

    def _execute_sql(self, result_type=MULTI, *, cursor):
        """
        Run the query against the database and return the result(s). The
        return value is a single data item if result_type is SINGLE, or an
        iterator over the results if the result_type is MULTI.

        result_type is either MULTI (use fetchmany() to retrieve all rows),
        SINGLE (only retrieve a single row), or None. In this last case, the
        cursor is returned if any query is executed, since it's used by
        subclasses such as InsertQuery). It's possible, however, that no query
        is needed, as the filters describe an empty set. In that case, None is
        returned, to avoid any unnecessary database interaction.
        """
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
                return RetCursor(cursor.rowcount)

        return execute_sql()


class SQLUpdateCompiler(SQLCompiler):
    def as_sql(self):
        return DjangoSQLUpdateCompiler.as_sql(self)

    def pre_sql_setup(self):
        return DjangoSQLUpdateCompiler.pre_sql_setup(self)

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

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def close(self):
        pass

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import cached_property

from django.db.backends.base.base import BaseDatabaseWrapper as _BaseDatabaseWrapper

from vinyl.futures import is_async


class BaseDatabaseWrapper(_BaseDatabaseWrapper):
    CursorWrapper = None

    @cached_property
    def async_connection(self):
        return ContextVar('async_connection', default=None)

    sync_connection = None

    def cursor_decorator(self, fn):
        async def awrapper(*args, **kwargs):
            async with self.cursor() as cursor:
                val = fn(*args, cursor=cursor, **kwargs)
                return await val

        def wrapper(*args, **kwargs):
            if not is_async():
                with self.cursor() as cursor:
                    val = fn(*args, cursor=cursor, **kwargs)
                    return val
            return awrapper(*args, **kwargs)

        return wrapper

    def cursor(self, fn=None):
        if callable(fn):
            return self.cursor_decorator(fn)
        if not is_async():
            return self.sync_cursor()

        @asynccontextmanager
        async def cursor():
            if self.async_pool is None:
                await self.start_pool()
            if (conn := self.async_connection.get()) is not None:
                async with conn.cursor() as cur:
                    if self.CursorWrapper:
                        cur = self.CursorWrapper(cur)
                    yield cur
                return
            async with self.get_connection_from_pool() as conn:
                token = self.async_connection.set(conn)
                try:
                    async with conn.cursor() as cur:
                        if self.CursorWrapper:
                            cur = self.CursorWrapper(cur)
                        yield cur
                finally:
                    self.async_connection.reset(token)
        return cursor()

    def get_connection_from_pool(self, pool):
        """
        return async context manager
        """
        raise NotImplementedError

    def get_cursor(self):
        return super().cursor()

    @contextmanager
    def sync_cursor(self):
        with self.sync_connection.cursor() as cur:
            if self.CursorWrapper:
                cur = self.CursorWrapper(cur)
            yield cur
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import cached_property

from django.db.backends.base.base import BaseDatabaseWrapper as _BaseDatabaseWrapper

from vinyl.futures import is_async


class BaseDatabaseWrapper(_BaseDatabaseWrapper):

    @cached_property
    def async_connection(self):
        return ContextVar('async_connection', default=None)

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
            return self.get_cursor()

        @asynccontextmanager
        async def cursor():
            if self.async_pool is None:
                await self.start_pool()
            if (conn := self.async_connection.get()) is not None:
                async with conn.cursor() as cur:
                    yield cur
                return
            async with self.async_pool.connection() as conn:
                token = self.async_connection.set(conn)
                try:
                    async with conn.cursor() as cur:
                        yield cur
                finally:
                    self.async_connection.reset(token)
        return cursor()

    def get_cursor(self):
        return super().cursor()

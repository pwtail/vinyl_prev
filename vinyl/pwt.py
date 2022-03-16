import asyncio
import inspect
import threading

import typing
from contextlib import contextmanager
from contextvars import ContextVar


def is_async():
    return threadlocal.IS_ASYNC

def set_async(value):
    threadlocal.IS_ASYNC = bool(value)


class RetCursor(typing.NamedTuple):
    rowcount: int

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def close(self):
        pass


def later(fn):
    assert not inspect.iscoroutinefunction(fn)
    sig = inspect.signature(fn)
    awaitables = [(k, v.default) for k, v in sig.parameters.items() if isinstance(v.default, typing.Awaitable)]

    async def awrapper(*args, **kwargs):
        for key, val in awaitables:
            try:
                kwargs[key] = await val
            except Exception as ex:
                kwargs[key] = ex
        val = fn(*args, **kwargs)
        if isinstance(val, typing.Awaitable):
            val = await val
        return val

    def wrapper(*args, **kwargs):
        if not is_async():
            return fn(*args, **kwargs)

        return awrapper(*args, **kwargs)

    return wrapper

wait = then = later

def value(val):
    @wait
    def f():
        return val
    return f()

wait.value = value
del value


def gather(*tasks):
    if not is_async():
        return tasks
    return asyncio.gather(*tasks)


def gen(fn):
    async def awrapper(*args, **kw):
        g = fn(*args, **kw)
        result = None
        while True:
            try:
                result = (await g.send(result))
            except StopIteration as ex:
                return ex.value

    def wrapper(*args, **kw):
        if is_async():
            return awrapper(*args, **kw)
        g = fn(*args, **kw)
        result = None
        while True:
            try:
                result = g.send(result)
            except StopIteration as ex:
                return ex.value

    return wrapper


threadlocal = threading.local()
threadlocal.IS_ASYNC = 1  # default


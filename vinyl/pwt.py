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


function = type(lambda: None)


class AbstractBranchWrapper:
    def __init__(self, type=None):
        self.wrappers = {}
        self.type = type

    def make_wrapper(self):
        raise NotImplementedError

    def __call__(self, fn=None, type=None, name=None):
        if type and not fn:
            return lambda func: self(func, type=type, name=name)
        if not type:
            if inspect.iscoroutinefunction(fn):
                type = 'async'
            else:
                type = 'sync'
        if not name:
            name = fn.__name__
        if name not in self.wrappers:
            wrapper = self.wrappers[name] = self.make_wrapper()
        else:
            wrapper = self.wrappers[name]
        if not hasattr(wrapper, 'options'):
            wrapper.options = [None, None]
        if type == 'sync':
            wrapper.options[0] = fn
        else:
            wrapper.options[1] = fn
        return wrapper


class BranchDescriptor(AbstractBranchWrapper):

    class Descriptor:
        options: list  # [sync_fn, async_fn]

        def __get__(self, instance, owner):
            if instance is None:
                return self
            func = self.options[is_async()]
            return func.__get__(instance)

    make_wrapper = Descriptor


class BranchWrapper(AbstractBranchWrapper):

    @staticmethod
    def make_wrapper():
        def wrapper(*args, **kw):
            options = wrapper.options
            if not is_async():
                sync_fn = options[0]
                assert inspect.isfunction(sync_fn) and not inspect.iscoroutinefunction(sync_fn)
                return sync_fn(*args, **kw)
            async_fn = options[1]
            return async_fn(*args, **kw)

        return wrapper


class Branch:
    Wrapper = BranchWrapper
    Descriptor = BranchDescriptor


class LazyObject(typing.NamedTuple):
    fn: function
    args: tuple
    kwargs: dict

    def __await__(self):
        (fn, args, kw) = self
        return fn(*args, **kw).__await__()

def lazyobj(fn):
    def wrapper(*args, **kw):
        if not is_async():
            return fn(*args, **kw)
        return LazyObject(fn, args, kw)

    return wrapper
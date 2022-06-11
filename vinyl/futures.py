import inspect
import threading
import typing


def is_async():
    return threadlocal.IS_ASYNC

def set_async(value):
    threadlocal.IS_ASYNC = bool(value)


threadlocal = threading.local()
threadlocal.IS_ASYNC = 1  # default


def later(fn):
    assert not inspect.iscoroutinefunction(fn)
    sig = inspect.signature(fn)

    async def awrapper(*args, **kwargs):
        default_kwargs = {
            k: v.default for k, v in sig.parameters.items() if isinstance(v.default, typing.Awaitable)
        }
        if default_kwargs and kwargs:
            kwargs = default_kwargs | kwargs
        elif default_kwargs:
            kwargs = default_kwargs
        for key, val in tuple(kwargs.items()):
            if isinstance(val, typing.Awaitable):  # or coroutine?
                try:
                    kwargs[key] = await val
                except Exception as ex:
                    if 'ex' not in sig.parameters:
                        raise
                    for k in tuple(kwargs.keys()):
                        kwargs[k] = return_none
                    kwargs[key] = kwargs['ex'] = Raise(ex)
                    break
        ret = fn(*args, **kwargs)
        if inspect.iscoroutine(ret):
            ret = await ret
        return ret

    def wrapper(*args, **kwargs):
        if not is_async():
            return fn(*args, **kwargs)

        return awrapper(*args, **kwargs)

    return wrapper


def value(val):
    @later
    def f():
        return val
    return f()

later.value = value
del value


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


def wrap_co(fn):
    async def wrapper(*args, **kw):
        return await fn(*args, **kw)
    return wrapper


class Raise:

    def __init__(self, ex):
        self.ex = ex

    def __call__(self):
        if ex := self.ex:
            self.ex = None
            raise ex


class ReturnNone:

    def __bool__(self):
        return False

    def __call__(self):
        return None


return_none = ReturnNone()

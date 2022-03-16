import asyncio
import inspect
import threading

import typing

from vinyl.futures import later


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


threadlocal = threading.local()
threadlocal.IS_ASYNC = 1  # default


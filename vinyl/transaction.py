from contextlib import asynccontextmanager, contextmanager

from vinyl.pwt import is_async


def atomic(using=None, savepoint=True, durable=False):
    if not is_async():
        return atomic_sync(using=using, savepoint=savepoint, durable=durable)

    return atomic_async(using=using, savepoint=savepoint, durable=durable)


@asynccontextmanager
def atomic_async(using=None, savepoint=True, durable=False):
    yield

@contextmanager
def atomic_sync(using=None, savepoint=True, durable=False):
    yield
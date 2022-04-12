"""Dealing with the lazy model attributes."""
from vinyl.futures import later
from vinyl.manager import _VinylManager
from vinyl.model import ensure_vinyl_model


class Lazy:

    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, name):
        manager = _VinylManager()
        manager.model = ensure_vinyl_model(self.obj._model)
        qs = manager.filter(pk=self.obj.pk)
        qs = qs.prefetch_related(name)
        qs._result_cache = [self.obj]

        @later
        def get(_=qs):
            [ob] = qs
            return getattr(ob, name)

        return get()

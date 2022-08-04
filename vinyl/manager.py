from django.db.models.manager import BaseManager, ManagerDescriptor
from django.db import models

from vinyl.meta import make_vinyl_model
from vinyl.queryset import VinylQuerySet


class _VinylManager(BaseManager.from_queryset(VinylQuerySet)):
    """
    VinylManager itself.
    """
    model = None

    # def __call__(self, *args, **kwargs):
    #     return self.model(*args, **kwargs)


class VinylManagerDescriptor(ManagerDescriptor):
    manager = None

    def __init__(self, model=None):
        self.manager = _VinylManager()
        if model:
            self.manager.model = model

    def __get__(self, instance, owner):
        assert not instance
        assert self.manager
        if not self.manager.model:
            self.manager.model = make_vinyl_model(owner)
            print('make')
        return self.manager

    def __set_name__(self, owner, name):
        assert issubclass(owner, models.Model)
        self.manager.name = name
        # assert not self.manager.model
        # self.manager.model = make_vinyl_model(owner)


VinylManager = VinylManagerDescriptor

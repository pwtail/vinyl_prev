from django.db.models.manager import BaseManager, ManagerDescriptor
from django.db import models

from vinyl.model import get_vinyl_model, VinylModel
from vinyl.queryset import VinylQuerySet


class _VinylManager(BaseManager.from_queryset(VinylQuerySet)):
    """
    VinylManager itself.
    """

    def __call__(self, *args, **kwargs):
        return self.model(*args, **kwargs)


class VinylManagerDescriptor(ManagerDescriptor):
    manager = None

    def __init__(self, model=None):
        self.manager = _VinylManager()
        self.manager.model = model

    def __get__(self, instance, owner):
        assert self.manager
        return self.manager

    def __set_name__(self, owner, name):
        assert issubclass(owner, models.Model)
        self.manager.name = name
        assert owner

        if not (model := self.manager.model):
            model = get_vinyl_model(owner)
            self.manager.model = model
        model._model = owner


VinylManager = VinylManagerDescriptor

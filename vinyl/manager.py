from django.db.models.manager import BaseManager, ManagerDescriptor

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
        super().__init__(model)

    def __get__(self, instance, owner):
        assert self.manager
        return self.manager

    def __set_name__(self, owner, name):
        self.manager = _VinylManager()
        self.manager.name = name
        assert owner
        if isinstance(owner, VinylModel):
            model = owner
        else:
            model = get_vinyl_model(owner)
        if not self.manager.model:
            self.manager.model = model


VinylManager = VinylManagerDescriptor
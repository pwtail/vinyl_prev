from django.db.models.base import ModelBase

from vinyl.futures import is_async, set_async
from vinyl.model import VinylModel

super__subclasscheck__ = ModelBase.__subclasscheck__
super__instancecheck__ = ModelBase.__instancecheck__


def __subclasscheck__(cls, subclass):
    if super__subclasscheck__(cls, subclass):
        return True
    return issubclass(subclass, VinylModel)


def __instancecheck__(cls, instance):
    if super__instancecheck__(cls, instance):
        return True
    return isinstance(instance, VinylModel)


ModelBase.__subclasscheck__ = __subclasscheck__
ModelBase.__instancecheck__ = __instancecheck__
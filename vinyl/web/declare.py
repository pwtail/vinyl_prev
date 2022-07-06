from functools import partial

from django.urls import path, URLPattern
from django.urls.conf import _path
from django.urls.resolvers import RoutePattern


def get(*args, **kwargs):
    kwargs['Pattern'] = RoutePattern
    p = _path(*args, **kwargs)
    if isinstance(p, URLPattern):
        p.method = 'get'
    return p

def post(*args, **kwargs):
    kwargs['Pattern'] = RoutePattern
    p = _path(*args, **kwargs)
    assert isinstance(p, URLPattern)
    p.method = 'post'
    return p

#
# class MyRoutePattern(RoutePattern):
#     def match(self, path):
#         match = super().match(path)
#         if match:
#             new_path, args, kwargs = match
#             return Path(new_path), args, kwargs
#

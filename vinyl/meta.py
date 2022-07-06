from django.db.models.query_utils import DeferredAttribute

from vinyl.model import ManagerProxy, FKeyProxy


class VinylMeta(type):

    def __new__(metacls, name, bases, namespace, **kw):
        MODULE = 'django.db.models.fields.related_descriptors'
        ns = dict(namespace)
        for key, val in namespace.items():
            if isinstance(val,
                          DeferredAttribute) or val.__class__.__module__ == MODULE:
                # print(key, val)
                if val.__class__.__name__.endswith('ToManyDescriptor'):
                    new_val = ManagerProxy(key, val)
                elif val.__class__.__name__.endswith('ToOneDescriptor'):
                    new_val = FKeyProxy(key, val)
                else:
                    new_val = FKeyProxy(key, val)
                ns[key] = new_val
        cls = super().__new__(metacls, name, bases, ns)
        return cls


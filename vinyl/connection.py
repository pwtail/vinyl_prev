
from django.db import connections as django_connections


class Connections:

    def __getitem__(self, item):
        item = f'vinyl_{item}'
        return django_connections[item]


connections = Connections()


class Connection:

    def __getattr__(self, item):
        conn = connections['default']
        return getattr(conn, item)


connection = Connection()
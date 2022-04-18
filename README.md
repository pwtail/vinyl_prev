# vinyl project: the async capabilities for django

*vinyl* is a third-party package that allows the existing 
django projects to be used in async context.

Unlike the approach taken by the
django project, it supports **native asynchrony**.

**Sync + async**

The distinctive feature of vinyl is that it provides both sync and async 
version that mirror each other 100%. To change the version used one should 
set the respective flag:

```python
from vinyl import set_async; set_async(true_or_false)
```

**The read and the write API's**

Generally speaking, *vinyl* has a full-blown read API similar to that of 
django (querysets and the like) and a restricted, minimalistic write API (`.
insert()`, `.update()` and `.delete()`)

**3 parts of vinyl**

- vinyl.connection

    The counterpart of `django.db.connection`. Encapsulates the driver. 
  Vinyl will support Postgresql, MariaDb and Mysql.

- The read API

  Speaks for itself

- The write API

  Utilities for working with objects

# vinyl project: the async capabilities for django

*vinyl* is a third-party package that allows the existing 
django projects to be used in async context.

Unlike the approach taken by the
django project, it supports **native asynchrony**.

**Seamless integration**

*vinyl* doesn't break the existing code of your projects, and can be used as 
a "plug-in".

It uses django extensibility features to a bit more extent than the official 
documentation recommends.
Indeed, django is pretty 
extensible, which is the result of the need to support a lot of database 
backends as well as multiple databases at once.

**VinylManager**

The entire async functionality is incapsulated in a models manager - 
`VinylManager`

```python
class Artifact(models.Model):
    ...
    vinyl = VinylManager()
```

The last row is all you need to add to your django models to start using 
*vinyl*.
Thus, the main entry point is still the model:

```python
from app.models import Artifact

if not await Artifact.vinyl.exists():
    ob = Artifact.vinyl(x=12)
    await ob.insert()
```

Queries using `vinyl` manager return instances of `VinylModel`. However, to 
create 
such an instance you have to explicitly use the manager: `MyModel.vinyl(**kwargs)`

**Sync and async**

*vinyl* provides both sync and async API, which reflect each other 100%. To 
use the sync version, all you have to do is to set the respective flag:

```python
from vinyl import set_async; set_async(False)
```

In addition to the sync version of *vinyl*, all of django functionality is 
still available. Actually, django provides a richer API, since 
*vinyl* is 
more 
minimalistic. Still, having the sync version is important for various 
reasons, the obvious ones being testability and documentation. The time will tell,
but I think, the sync version of *vinyl* will be used widely too.

**Minimalistic write API**

As was said already, *vinyl*'s API is more minimalistic than django's. 
That's because not all 
decisions in django are a good fit for a universal framework, supporting both 
sync 
and async modes.

Regarding the query builder (working with querysets), *vinyl* almost fully 
copies the 
django API. The querysets are lazy in django, so this is pretty cheap to 
support. This is the API for reading data from the database.

Speaking of the CRUD operations with objects (model instances), the API 
starts to be different, being more minimalistic and more explicit. 
For example, currently, there is no `obj.save()` method, with `.insert()` and `.
update()` being provided instead. This is the API for write operations.

A simpler write API eliminates the need to track complex chains of related 
objects to calculate the sequence of writes that need to be 
performed.

**Lazy attributes**

Django is well-known for its lazy attributes, fetching the related entities 
on demand under the hood. I decided not to support that feature in full in 
*vinyl*.

However, if you have have prefetched all the related entities, than you can use 
the 
related attributes (without `await`). Trying to access attributes that 
haven't been fetched will result in an error.

If you do need to make a query, you should 
mark that explicitly by using the `.q` attribute:

```python
await obj.q.related_obj
```

There is a nice trick to easily support a lot of django API (the read-only part 
of it). Can you guess how? I could: first you make a `prefetch_related`, and than return the attributes.
So, again, the read API can be implemented pretty easily.

The write operations like `obj.collection.add(item)` probably won't be 
supported, so you will have to use CRUD operations provided by vinyl.

**Model classes**

By default, *vinyl* will create subclasses of `VinylModel` for your django 
models for you. But you can create these classes explicitly if you want, and 
start 
adding custom methods to it. Than the model should be passed to 
`VinylManager` as argument.

```python
# custom.py

class Artifact(VinylModel):

    async def insert(self):
        await super().insert()
        print(f"inserted: {self.pk}")

# models.py

class Artifact(models.Model):
    ...
    vinyl = VinylManager(model=custom.Artifact)
```

**Features that are not supported**

Signals are gone in *vinyl*. So is the lazy iteration of querysets, 
intended for cases when the 
result of a queryset doesn't fit into the memory (a really half-baked 
feature in django, that was used rarely anyway).

**Database support**

*vinyl* aims to support Postgresql, MariaDb and MySql. The latter two are 
pretty similar so that means 2 database backends with sync and async drivers.
Among the open-source databases, there is also Sqlite, of course, which the 
author admires much, but its usecase is usually pretty different.

**Compatibility with django, vinyl's approach**

*vinyl* is intended for django projects and is based on the django codebase. 
However it is largely independent code, in a sense that it doesn't fork django 
and is almost unaffected by the particular version of django used.

So, *vinyl* has relative freedom to change things, and it uses that freedom for 
its benefit.

As a rule, one should be able to use existing models as they are with 
*vinyl*.

However, there is intention to make the rules of models inheritance more 
strict, given that covers the majority of usecases. For example, to allow 
to inherit from a single concrete model only, so that all models in the 
inheritance chain would share the same primary key. This can probably simplify 
things a lot, and will 
make easier for bulk operations to support inheritance too. 
Of course, there 
can be utility 
functions for working with existing setups.

**Unique features. The summary**

In my opinion, *vinyl* proposed the first adequate approach enabling the 
use of the async 
code in django projects.

Also, it is the first ORM that supports both sync and async 
modes. This 
opens 
the way to having a web application that has both ASGI and WSGI endpoints 
sharing 
the same environment (and the database of course).

Also, it is a shameless try to revive django (which the most of developers 
are fed up with!), which without the async features is doomed to extinction.

Also, *vinyl*, being minimalistic in some aspects, still provides far 
reacher functionality than many other pure-async frameworks.

Happy coding and good luck with *vinyl*!
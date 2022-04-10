# vinyl project: the async capabilities for django

*vinyl* is a third-party package that allows existing 
django projects to be used in async context. Unlike the approach taken by the
django project, it supports **native asynchrony**.

**Seamless integration**

*vinyl* doesn't break the existing code of your projects, and can be used as 
a plug-in.

It uses django extensibility features to a bit more extent than the official 
documentation recommends.
Indeed, django is pretty 
extensible, which is the result of the need of supporting a lot of database 
backends as well as supporting multiple databases at once.

**VinylManager**

The entire async functionality is incapsulated in a models manager - 
`VinylManager`

```python
class Artifact(models.Model):
    ...
    vinyl = VinylManager()
```

The last row is all you need to add to your django models to start using vinyl.
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

**Minimalistic API**

As ws said, *vinyl* provides a more minimalistic API. Not all 
decisions in django are a good fit for a universl framework, supporting sync 
and async usecases at the same time.

Regarding the query builder (queryset usage), *vinyl* fully copies the 
django API. The querysets are lazy in django, so this is pretty cheap to 
provide.

Speaking of the CRUD operations with objects (model instances), the API 
starts to be different, being more minimalistic and more explicit. 
For example, currently, there is no `obj.save()` method, with `.insert()` and `.
update()` being provided instead.

Model inheritance is currently supported as-is, but there is a plan to cut 
that functionality down a bit too. For example, to allow to inherit from one 
concrete model at most, thus forcing all inheritance chain to have the same 
primary key. This will greatly simplify things, and will make possible to 
make bulk operations aware of inheritance chains too.

**Lazy attributes**

Django is well-known for its lazy attributes, fetching the related entities 
under the hood implicitly. I decided not to support that fully in *vinyl*.

What is supported: if you have prefetched those attributes in previous 
queries (using `prefetch_related`, for example), than you can use them, 
otherwise not. Otherwise you have to use the CRUD operations with model 
instances directly.

This decision allows to use the model fields as they are in django.

As a summarizing note, the *vinyl* API, being minimalistic, still provides far 
reacher functionality than many other pure-async frameworks.

**Other features that are not supported**

Signals are gone in *vinyl*. So is the lazy iteration of querysets, when the 
result of the queryset doesn't fit in the memory (a really half-baked 
feature in django, that is used very rarely).

**Model classes**

By default, *vinyl* will create subclasses of `VinylModel` for your django 
models by default. But you can create these classes explicitly if you want, and 
start 
adding custom methods to it. Than it should be passed to `VinylManager` as 
shown below.

```python
# custom.py

class Artifact(VinylModel):

    async def insert(self):
        pass

# models.py

class Artifact(models.Model):
    ...
    vinyl = VinylManager(model=custom.Artifact)
```

**Database support**

*vinyl* aims to support Postgresql, MariaDb and MySql. The latter two are 
pretty similar so that means 2 database backends with sync and async drivers.
Among the open-source databases, there is also Sqlite, of course, which the 
author admires much, but its usecase is usually pretty different.

**Compatibility with django, vinyl's approach**

*vinyl* is intended for django projects and is based on the django codebase, 
however it is largely independent code, in a sense that it doesn't fork django 
and is almost unaffected by the particular version of django used.

So, `vinyl` has relative freedom to change things, and is 
going to use that for its own benefit.

Generally speaking, one should be able to use existing models as they are with 
*vinyl*.
However, there is intention to make the rules of models inheritance more 
strict, given that covers the majority of usecases. There could be utility 
functions for working with existing setups, of course.

*vinyl* does change the API for CRUD operations with objects and does not 
support lazy attributes that need to fetch data on demand.

**Unique features. The summary**

First of all, *vinyl* is the first ORM that supports both sync and async 
modes (actually there is a third mode too which is vanilla django). That 
opens 
the way to have a web application that has both ASGI and WSGI endpoints sharing 
the same environment (and the database of course).

Next, it is the only project that provides integration between your django 
project and your asynchronous code. So, large projects using django probably 
should be interested.

Also, it is a shameless try to revive django (which the most of developers 
are fed up with!), which without the async features is doomed to extinction.

**Further development**

I don't think that such a project (adding async capabilities to django) 
should be developed as a personal project. It is not that, it's actually the 
further 
development of django. So the author will probably do all the development as an 
employee of a company that uses django extensively.
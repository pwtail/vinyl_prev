# vinyl project - asynchrony for django

*vinyl* is a third-party package that adds async capabilities to existing 
django projects. Unlike the approach taken by django project, it is native 
asynchrony that is supported.

**Seamless integration**

It doesn't break the existing code of your projects, and uses `django` as a 
dependency (instead of forking it). reused

*vinyl* uses django extensibility features a bit more than the official documentation recommends.
Indeed, django is pretty 
extensible, as a result of the need of supporting a lot of database 
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
Thus, the main entry point is still the models:

```python
from app.models import Artifact

if not await Artifact.vinyl.exists():
    ob = Artifact.vinyl(x=12)
    await ob.insert()
```

Queries using `vinyl` manager return instances of `VinylModel`. To create 
such an instance you have to explicitly use the manager: `MyModel.vinyl
(**kwargs)`

**Sync and async**

*vinyl* provides both sync and async API, which reflect each other 100%. To 
use the sync version, all you have to do is set the respective flag:

```python
from vinyl import set_async; set_async(False)
```

In addition to the sync version of *vinyl*, of course, all of django is 
still available, and django provides more capabilites, since *vinyl* is more 
minimalistic. Still, I think, having sync version is important for various 
reasons, the obvious ones being testability and documentation.

The time will tell, but I think, the sync version of *vinyl* will be used 
widely too.

**Minimalistic API**

*vinyl* is independent from django code-wise, so it's an opportunity to 
make things different and better, from a certain perspective. Not all 
decisions in django are a good fit for a universl framework, supporting sync 
and async usecase at the same time.

Regarding the query builder (queryset usage), *vinyl* fully copies the 
django API. The querysets are lazy in django, so this is pretty cheap to 
provide.

Speaking of the CRUD operations with objects (model instances), the API 
starts to be different, providing more minimalistic (and more explicit) API. 
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
models on demand. But you can create these classes explicitly, and start 
adding custom methods to it.

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

Особенности:

- синхронный и (нативный) асинхронный I/O, поддержанный одной кодовой базой
- можно использовать в имеющихся django проектах: есть совместимость с 
  django по 
  моделям.

Будут поддерживаться базы Postgresql, MariaDb, Mysql

Что касается запросов (querysets), проект сохранит апи django как он есть. 
  Что касается действий с объектами (инстансами моделей), апи станет гораздо 
  более минималистичным.

Несмотря на то, что django уже является синхронным 
фреймворком, vinyl будет также содержать свою синхронную версию, апи которой 
будет зеркальным отражением асинхронной версии. Таким образом, vinyl 
будет независимым от django фреймворком.

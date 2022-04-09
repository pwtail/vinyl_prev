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

```




**Sync and async**

For example, qs


model classes are supported

WIP


vinyl - реинкарнация django с поддержкой асинхронности.

seamlessly in django projects

3rd party

VinylManager()

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

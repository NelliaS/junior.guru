import json
from pathlib import Path
from collections.abc import Set
from functools import wraps

import scrapy
from peewee import Model, SqliteDatabase
from playhouse.sqlite_ext import JSONField as BaseJSONField

from juniorguru.lib import loggers


logger = loggers.get('db')


db_file = Path(__file__).parent / '..' / 'data' / 'data.db'
db = SqliteDatabase(db_file, check_same_thread=False,
                    pragmas={'journal_mode': 'wal'})


class BaseModel(Model):
    class Meta:
        database = db


class JSONField(BaseJSONField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('json_dumps', json_dumps)
        super().__init__(*args, **kwargs)


def json_dumps(value):
    def default(o):
        if isinstance(o, scrapy.Item):
            return dict(o)
        if isinstance(o, Set):
            return list(o)
        try:
            return o.isoformat()
        except AttributeError:
            raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')

    return json.dumps(value, ensure_ascii=False, default=default)


def with_db(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with db:
            return fn(*args, **kwargs)
    return wrapper

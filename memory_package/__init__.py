from .in_memory_vars import logger, orders_lock, increment_calls_count, set_calls_count
from .db_abstract import AbstractDb
from .in_memory_db.in_memory_db import InMemoryDb

db: AbstractDb = InMemoryDb()


def reset_db():
    global db
    db = InMemoryDb()
    print(db.get_clients_count())

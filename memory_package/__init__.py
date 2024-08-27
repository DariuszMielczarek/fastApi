from .in_memory_vars import logger, orders_lock, increment_calls_count, set_calls_count
from .db_abstract import AbstractDb
from .in_memory_db.in_memory_db import InMemoryDb
from .postgres_db.postgres_db import PostgresDb, Order as OrderPostgres, Client as ClientPostgres
from client_package import Client

db: AbstractDb = PostgresDb()
db_type: str = 'postgres'

db_classes = {
    'in_memory': InMemoryDb,
    'postgres': PostgresDb
}


def reset_db():
    global db
    db = db_classes[db_type]()


def mapper(client):
    return Client.model_validate(client).model_dump()

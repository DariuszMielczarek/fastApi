import copy

from pydantic import BaseModel

from blocking_list import BlockingList
from order_package import Order
from .in_memory_vars import orders_lock

orders_db = BlockingList()
clients_db = BlockingList()


class ClientBase(BaseModel):
    name: str
    orders: list[Order] = []
    photo: str = str()


class Client(ClientBase):
    password: str = Ellipsis


class ClientOut(ClientBase):
    pass


class ClientInDb(BaseModel):
    name: str
    orders: list[Order] = list()
    password: str = Ellipsis
    photo: str = str()
    id: int


def set_new_orders_db(new_ordersDb: BlockingList):
    global orders_db
    orders_db = copy.deepcopy(new_ordersDb)


def set_new_clients_db(new_clients_db: BlockingList):
    global clients_db
    clients_db = copy.deepcopy(new_clients_db)


async def get_all_orders_as_dict():
    async with orders_lock:
        return [order.model_dump() for order in orders_db]


async def get_first_order_with_status(status_str: str):
    async with orders_lock:
        return next((order for order in orders_db if order.status.value == status_str), None)


def get_order_by_id(order_id: int):
    return next((order for order in orders_db if order.id == order_id), None)


def add_order(order):
    orders_db.append(order)


def add_client(client):
    client_id = get_next_client_id()
    clients_db.append(ClientInDb(**client.model_dump(), id=client_id))
    return client_id


def add_order_to_client(order, client):
    client.orders.append(order)


def get_client_by_name(full_name: str):
    return next((client for client in clients_db if client.name == full_name), None)


def get_clients_by_ids(client_ids: list[int]):
    return [client for client in clients_db if client.id in client_ids]


def get_client_by_id(client_id: int):
    return get_clients_by_ids([client_id])[0] if get_clients_by_ids([client_id]) else None


def get_clients_db(count: int = None):
    return clients_db[:count] if count else clients_db


def get_orders_db():
    return orders_db


def remove_order(order: Order):
    orders_db.remove(order)


def remove_client(client: ClientInDb):
    clients_db.remove(client)


def get_next_order_id():
    return 0 if len(get_orders_db()) == 0 else max(get_orders_db(), key=lambda order: order.id).id + 1


def get_next_client_id():
    return 0 if len(get_clients_db()) == 0 else max(get_clients_db(), key=lambda client: client.id).id + 1


def get_clients_count():
    return len(clients_db)


def get_orders_count():
    return len(orders_db)


def get_password_from_client_by_name(full_name: str):
    client = get_client_by_name(full_name)
    return client.password if client else None


def get_orders_by_client_id(client_id: int):
    clients = get_clients_by_ids([client_id])
    return clients[0].orders if len(clients) > 0 else None


def get_orders_by_client_name(client_name: str):
    client = get_client_by_name(client_name)
    return client.orders if client else None


def clear_db():
    orders_db.clear()
    clients_db.clear()


def open_dbs():
    orders_db.unblock()
    clients_db.unblock()


def close_dbs():
    orders_db.block()
    clients_db.block()

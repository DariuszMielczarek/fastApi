import copy

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from order_package import Order
from .in_memory_vars import orders_lock

ordersDb = []
clientsDb = []


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


def set_new_ordersDb(new_ordersDb : list):
    global ordersDb
    ordersDb = copy.deepcopy(new_ordersDb)


async def get_all_orders_as_dict():
    async with orders_lock:
        print(ordersDb)
        return [order.dict() for order in ordersDb]


async def get_first_order_with_status(status_str: str):
    async with orders_lock:
        return next((order for order in ordersDb if order.status.value == status_str), None)


async def get_order_by_id(order_id: int):
    async with orders_lock:
        return next((order for order in ordersDb if order.id == order_id), None)


def add_order(order):
    ordersDb.append(order)


def add_client(client):
    client_id = get_next_client_id()
    clientsDb.append(ClientInDb(**client.model_dump(), id=client_id))
    return client_id


def add_order_to_client(order, client):
    client.orders.append(order)


def get_client_by_name(full_name: str):
    return next((client for client in clientsDb if client.name == full_name), None)


def get_clients_by_ids(client_ids: list[int]):
    return [client for client in clientsDb if client.id in client_ids]


def get_clientsDb(count: int = None):
    return clientsDb[:count] if count else clientsDb


def get_ordersDb():
    return ordersDb


def remove_order(order: Order):
    ordersDb.remove(order)


def get_next_order_id():
    return 0 if len(get_ordersDb()) == 0 else max(get_ordersDb(), key=lambda order: order.id).id + 1


def get_next_client_id():
    return 0 if len(get_clientsDb()) == 0 else max(get_clientsDb(), key=lambda client: client.id).id + 1


def get_clients_count():
    return len(clientsDb)


def get_orders_count():
    return len(ordersDb)


def get_password_from_client_by_name(full_name: str):
    client = get_client_by_name(full_name)
    return client.password if client else None


def get_orders_by_client_id(client_id: int):
    clients = get_clients_by_ids([client_id])
    return clients[0].orders if len(clients) > 0 else None


def get_orders_by_client_name(client_name: str):
    client = get_client_by_name(client_name)
    return client.orders if client else None

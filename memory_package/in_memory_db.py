import copy
import random

from pydantic import BaseModel
from order_package import Order
from .in_memory_vars import orders_lock

ordersDb = []
clientsDb = []


class ClientBase(BaseModel):
    name: str
    orders: list[Order] = []


class Client(ClientBase):
    password: str = Ellipsis


class ClientOut(ClientBase):
    pass


class ClientInDb(BaseModel):
    name: str
    orders: list[Order] = list()
    password: str = Ellipsis
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
    clientsDb.append(ClientInDb(**client.dict(), id=random.randint(1, 1000)))
    print(clientsDb)


def get_client_by_name(full_name: str):
    return next((client for client in clientsDb if client.name == full_name), None)


def get_clients(count: int = None):
    return clientsDb[:count] if count else clientsDb


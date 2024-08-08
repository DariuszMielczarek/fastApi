import copy

from .in_memory_vars import orders_lock

ordersDb = []
clientsDb = []


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


def add_order(order):
    ordersDb.append(order)

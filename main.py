import asyncio
import logging
import sys
from asyncio import sleep, Task, Lock
from typing import Annotated

from fastapi import Body, FastAPI, Query
from pydantic import BaseModel
from enum import Enum

from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    received = 'received'
    in_progress = 'in_progress'
    complete = 'complete'


class Order(BaseModel):
    id: int
    description: str
    time: int = 60
    status: OrderStatus = OrderStatus.received
    client_name: str


class OrderDTO(BaseModel):
    description: str
    time: int = 60


class Client(BaseModel):
    name: str = Ellipsis
    orders: list[Order] = []


ordersDb = []
clientsDb = []
orders_lock = asyncio.Lock()
app = FastAPI()


@app.post('/orders/process')
async def process_order_respond():
    async with orders_lock:
        order = next((order for order in ordersDb if order.status == OrderStatus.received), None)
    if order is None:
        logger.warning("No awaiting order")
        return JSONResponse(status_code=400, content={"message": "No awaiting order"})
    else:
        asyncio.create_task(process_order(order))
        logger.info("Processing order")
        return JSONResponse(status_code=201, content={"message": "Success", "orderId": order.id})


async def process_order(order: Order):
    task = asyncio.create_task(process_simulator(order))
    async with orders_lock:
        order.status = OrderStatus.in_progress
    await task
    logger.info("Finished processing order")
    async with orders_lock:
        order.status = OrderStatus.complete


@app.post('/users/add')
async def add_user_without_task(client_name1: Annotated[str, Query(min_length=3, max_length=30, pattern="^.+$", title="Main name", description="Obligatory part of the name")], client_name2: Annotated[str | None, Query(min_length=3, max_length=30, pattern="^.+$", deprecated=True)] = None, names: Annotated[list[str] | None, Query(alias="Lista dodatków do nazwy :)")] = None):
    async with orders_lock:
        full_name = client_name1 if client_name2 is None else client_name1 + client_name2
        if names is not None:
            for name in names:
                full_name += name
        client = next((client for client in clientsDb if client.name == full_name), None)
        if client is None:
            clientsDb.append(Client(name=full_name))
            logger.info(f"Created new client without orders with name {full_name}")
            return JSONResponse(status_code=201, content={"message": "Success"})
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=400, content={"message": "Name used"})


@app.post('/orders/{client_name}')
async def create_order(client_name: str, orderDto: OrderDTO | None = None):
    if orderDto is None:
        logger.warning('No order')
        return JSONResponse(status_code=400, content={"message": "No order"})
    async with orders_lock:
        new_order = map_orderDto_to_Order(orderDto, client_name)
        client = next((client for client in clientsDb if client.name == client_name), None)
        if client is None:
            clientsDb.append(Client(name=client_name, orders=[new_order]))
            logger.info('Created new client')
        else:
            client.orders.append(new_order)
            logger.info('Added new order to the existing client')
        ordersDb.append(new_order)
    return JSONResponse(status_code=201, content={"message": "Success"})


@app.get('/orders/get/all')
async def get_orders():
    logger.info('Return all orders list ')
    async with orders_lock:
        return_dict = [order.dict() for order in ordersDb]
    return JSONResponse(status_code=201, content={"message": "Success", "orders": return_dict})


@app.get('/orders/get/{client_name}')
async def get_orders_by_client(client_name: str):
    async with orders_lock:
        client = next((client for client in clientsDb if client.name == client_name), None)
    if client is not None:
        logger.info(f"Return user''s {client_name} orders list")
        async with orders_lock:
            return_dict = [order.dict() for order in client.orders]
        return JSONResponse(status_code=201, content={"message": "Success", "orders": return_dict})
    else:
        logger.warning(f"No user with name: {client_name}")
        return JSONResponse(status_code=400, content={"message": "Incorrect username"})


@app.get('/orders/get/status/{status_name}')
async def get_orders_by_status(status_name: OrderStatus):
    async with orders_lock:
        logger.info(f"Return orders with status = {status_name.value} list")
        return_dict = [order.dict() for order in ordersDb if order.status == status_name]
        return JSONResponse(status_code=201, content={"message": "Success", "orders": return_dict})


@app.delete('/orders/remove')
async def delete_orders_of_ids(first: int = 0, last: int = sys.maxsize):
    if last < first:
        logger.warning(f"Tried to remove order with greater first id then last id")
        return JSONResponse(status_code=400, content={"message": "First id greater than last id"})
    global ordersDb
    removed_orders_count = 0
    async with orders_lock:
        for order in ordersDb:
            if first <= order.id <= last:
                ordersDb.remove(order)
                logger.info(f"Removing order with id {order.id}")
                client = next((client for client in clientsDb if client.name == order.client_name), None)
                client.orders.remove(order)
                removed_orders_count += 1
    return JSONResponse(status_code=201, content={"message": "Success", "removed_count": removed_orders_count})


@app.delete('/orders/{order_id}')
async def delete_order(order_id: int):
    global ordersDb
    async with orders_lock:
        removed_order = next((order for order in ordersDb if order.id == order_id), None)
        if removed_order:
            ordersDb = [order for order in ordersDb if order.id != order_id]
            logger.info(f"Removing order with id {order_id}")
            client = next((client for client in clientsDb if client.name == removed_order.client_name), None)
            client.orders.remove(removed_order)
            return JSONResponse(status_code=201, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            return JSONResponse(status_code=400, content={"message": "No such order"})


@app.get('/')
def send_app_info():
    return JSONResponse(status_code=201, content={"message": "Success", "tasks_count": len(ordersDb)})


def get_next_order_id():
    return 0 if len(ordersDb) == 0 else max(ordersDb, key=lambda order: order.id).id + 1


def map_orderDto_to_Order(orderDto: OrderDTO, client_name: str):
    return Order(id=get_next_order_id(), description=orderDto.description, time=orderDto.time, client_name=client_name)


async def process_simulator(order: Order):
    await sleep(order.time)

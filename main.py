import asyncio
import logging
from asyncio import sleep, Task

from fastapi import Body, FastAPI
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


class OrderDTO(BaseModel):
    description: str
    time: int = 60


class Client(BaseModel):
    name: str
    orders: list[Order] | None = None


ordersDb = []
clientsDb = []
app = FastAPI()


@app.post('/orders/process')
async def process_order_respond():
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
    order.status = OrderStatus.in_progress
    await task
    logger.info("Finished processing order")
    order.status = OrderStatus.complete


@app.post('/orders/{client_name}')
async def create_order(client_name: str, orderDto: OrderDTO | None = None):
    if orderDto is None:
        logger.warning('No order')
        return JSONResponse(status_code=400, content={"message": "No order"})
    new_order = map_orderDto_to_Order(orderDto)
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
    return_dict = [order.dict() for order in ordersDb]
    return JSONResponse(status_code=201, content={"message": "Success", "orders": return_dict})


@app.get('/orders/get/{client_name}')
async def get_orders_by_client(client_name: str):
    client = next((client for client in clientsDb if client.name == client_name), None)
    if client is not None:
        logger.info(f"Return user''s {client_name} orders list")
        return_dict = [order.dict() for order in client.orders]
        return JSONResponse(status_code=201, content={"message": "Success", "orders": return_dict})
    else:
        logger.warning(f"No user with name: {client_name}")
        return JSONResponse(status_code=400, content={"message": "Incorrect username"})


def get_next_order_id():
    return 0 if len(ordersDb) == 0 else max(ordersDb, key=lambda order: order.id).id + 1


def map_orderDto_to_Order(orderDto: OrderDTO):
    return Order(id=get_next_order_id(), description=orderDto.description, time=orderDto.time)


async def process_simulator(order: Order):
    await sleep(order.time)

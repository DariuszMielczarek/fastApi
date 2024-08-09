import asyncio
import sys
from typing import Annotated
from fastapi import Body, FastAPI, Query, Path, Cookie, Header
from starlette import status
from starlette.responses import JSONResponse, Response

import memory_package
from memory_package import clientsDb, ordersDb, orders_lock, logger, set_new_ordersDb, get_all_orders_as_dict, \
    get_first_order_with_status, add_order, get_order_by_id, add_client, get_client_by_name, ClientOut, Client
from orders_management_package import OrderDTO
from order_package import Order, OrderStatus
from orders_management_package.process_order import process_order


app = FastAPI()


@app.post('/orders/process')
async def process_next_order() -> JSONResponse:
    order = await get_first_order_with_status(OrderStatus.received)
    if order is None:
        logger.warning("No awaiting order")
        return JSONResponse(status_code=400, content={"message": "No awaiting order"})
    else:
        asyncio.create_task(process_order(order))
        logger.info("Processing order")
        return JSONResponse(status_code=201, content={"message": "Success", "orderId": order.id})


@app.post('/orders/process/{order_id}')
async def process_order_of_id(order_id: Annotated[int, Path(title="Order to process", ge=0)],
                              resp_fail1: Annotated[str | None, Body()] = "No such order",
                              resp_fail2: Annotated[str | None, Body()] = "Order does not await for process",
                              resp_success: str | None = "Success") -> Response:
    order = await get_order_by_id(order_id)
    if order is None:
        logger.warning(f"No awaiting order with id = {order_id}")
        return JSONResponse(status_code=400, content={"message": resp_fail1})
    elif order.status != OrderStatus.received:
        logger.warning(f"Order with id = {order_id} has wrong status")
        return JSONResponse(status_code=400, content={"message": resp_fail2})
    else:
        asyncio.create_task(process_order(order))
        logger.info(f"Processing order with id = {order_id}")
        return JSONResponse(status_code=201, content={"message": resp_success, "orderId": order.id})


@app.post('/clients/add', response_model_exclude_unset=True, response_model=None)
async def add_client_without_task(client_name1: Annotated[str, Query(min_length=3, max_length=30, pattern="^.+$", title="Main name", description="Obligatory part of the name")],
                                client_name2: Annotated[str | None, Query(min_length=3, max_length=30, pattern="^.+$", deprecated=True)] = None,
                                passwords: Annotated[list[str] | None, Query(alias="List of parts of password :)")] = None) -> Response | ClientOut:
    async with orders_lock:
        full_name = client_name1 if client_name2 is None else client_name1 + client_name2
        client = get_client_by_name(full_name)
        if client is None:
            if passwords is None:
                password = "123"
            else:
                password = "".join(passwords)
            add_client(Client(name=full_name, password=password))
            logger.info(f"Created new client without orders with name {full_name}")
            return ClientOut(name=full_name)
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=400, content={"message": "Name used"})


@app.get('/clients/', response_model=list[ClientOut])
async def get_clients(count: Annotated[int | None, Query(gt=0)] = None):
    return memory_package.get_clients(count)


@app.post('/orders/{client_name}')
async def create_order(client_name: str, orderDto: Annotated[OrderDTO | None, Body()] = None):
    if orderDto is None:
        logger.warning('No order')
        return JSONResponse(status_code=400, content={"message": "No order"})
    async with orders_lock:
        new_order = map_orderDto_to_Order(orderDto, client_name)
        client = next((client for client in clientsDb if client.name == client_name), None)
        if client is None:
            add_client(Client(name=client_name, password="123", orders=[new_order]))
            logger.info('Created new client')
        else:
            client.orders.add(new_order)
            logger.info('Added new order to the existing client')
        add_order(new_order)
    return JSONResponse(status_code=201, content={"message": "Success"})


@app.get('/orders/get/all', response_model=list[Order], status_code=status.HTTP_202_ACCEPTED)
async def get_orders():
    logger.info('Return all orders list ')
    return_dict = await get_all_orders_as_dict()
    return return_dict


@app.get('/orders/get/headers')
async def get_orders_counts_from_header(clients_names: Annotated[str | None, Header()] = None):
    async with orders_lock:
        if clients_names:
            clients_names_list = clients_names.split(',')
        else:
            clients_names_list = []
        print(clients_names_list)
        clients = [client for client in clientsDb if client.name in clients_names_list]
    if len(clients) > 0:
        results = []
        for client in clients:
            logger.info(f"Return user''s {client.name} orders count from header")
            async with orders_lock:
                results.append(len(client.orders))
        return JSONResponse(status_code=201, content={"message": "Success", "clients_orders_count": results})
    else:
        logger.warning(f"No user with names given in header")
        return JSONResponse(status_code=400, content={"message": "Incorrect header values"})


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
    orders_to_remove = []
    async with orders_lock:
        for order in ordersDb:
            if first <= order.id <= last:
                orders_to_remove.append(order)
        for order in orders_to_remove:
            ordersDb.remove(order)
            logger.info(f"Removing order with id {order.id}")
            client = next((client for client in clientsDb if client.name == order.client_name), None)
            client.orders.remove(order)
    return JSONResponse(status_code=201, content={"message": "Success", "removed_count": len(orders_to_remove)})


@app.delete('/orders/{order_id}')
async def delete_order(order_id: int):
    async with orders_lock:
        removed_order = next((order for order in ordersDb if order.id == order_id), None)
        if removed_order:
            new_ordersDb = [order for order in ordersDb if order.id != order_id]
            set_new_ordersDb(new_ordersDb)
            logger.info(f"Removing order with id {order_id}")
            client = next((client for client in clientsDb if client.name == removed_order.client_name), None)
            client.orders.remove(removed_order)
            return JSONResponse(status_code=201, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            return JSONResponse(status_code=400, content={"message": "No such order"})


@app.get('/')
def send_app_info(ads_id: Annotated[str | None, Cookie()]):
    if ads_id is not None:
        logger.info('We have cookie value: ' + ads_id)
    return JSONResponse(status_code=201, content={"message": "Success", "ads_id": ads_id, "tasks_count": len(ordersDb)})


@app.post('/orders/swap/{order_id}')
async def swap_orders_client(order_id: int, client_name: Annotated[str | None, Query(openapi_examples={
                "normal": {
                    "summary": "Normal example",
                    "description": "A **normal** item works correctly.",
                    "value": "Bob"
                },
                "converted": {
                    "summary": "Empty example",
                    "description": "**Empty** ***None*** works correctly",
                    "value": "None"
                }
            })] = None):
    async with orders_lock:
        swapped_order = next((order for order in ordersDb if order.id == order_id), None)
        if swapped_order:
            logger.info(f"Swapping client of order with id {order_id}")
            old_client = next((client for client in clientsDb if client.name == swapped_order.client_name), None)
            old_client.orders.remove(swapped_order)
            swapped_order.client_name = client_name
            if client_name is not None:
                new_client = next((client for client in clientsDb if client.name == swapped_order.client_name), None)
                if new_client is None:
                    clientsDb.append(Client(name=client_name, orders=[swapped_order]))
                    logger.info('Created new client')
                else:
                    new_client.orders.add(swapped_order)
                    logger.info('Added new order to the existing client')
            return JSONResponse(status_code=201, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            return JSONResponse(status_code=400, content={"message": "No such order"})


def get_next_order_id():
    return 0 if len(ordersDb) == 0 else max(ordersDb, key=lambda order: order.id).id + 1


def map_orderDto_to_Order(orderDto: OrderDTO, client_name: str):
    return Order(id=get_next_order_id(), description=orderDto.description,
                 time=orderDto.time, client_name=client_name, creation_date=orderDto.timestamp.isoformat())

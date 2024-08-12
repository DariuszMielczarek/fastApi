import asyncio
import sys
from typing import Annotated
from fastapi import Body, FastAPI, Query, Path, Cookie, Header, Form, UploadFile, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import memory_package
from exceptions import NoOrderException
from memory_package import logger, orders_lock, Client, ClientOut
from orders_management_package import OrderDTO
from order_package import Order, OrderStatus
from orders_management_package.process_order import process_order
from tags import Tags

app = FastAPI()


@app.exception_handler(NoOrderException)
async def no_order_exception_handler(request: Request, exc: NoOrderException):
    return JSONResponse(
        status_code=404,
        content={"message": exc.message if exc.message is not None else "ID: " + str(exc.order_id) + ") No order"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


@app.post('/orders/process', tags=[Tags.order_process], deprecated=True)
async def process_next_order() -> JSONResponse:
    order = await memory_package.get_first_order_with_status(OrderStatus.received)
    if order is None:
        logger.warning("No awaiting order")
        raise NoOrderException(message="No awaiting order")
    else:
        asyncio.create_task(process_order(order))
        logger.info("Processing order")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orderId": order.id})


@app.post('/orders/process/{order_id}', tags=[Tags.order_process])
async def process_order_of_id(order_id: Annotated[int, Path(title="Order to process", ge=0)],
                              resp_fail1: Annotated[str | None, Body()] = "No such order",
                              resp_fail2: Annotated[str | None, Body()] = "Order does not await for process",
                              resp_success: str | None = "Success") -> Response:
    order = await memory_package.get_order_by_id(order_id)
    if order is None:
        logger.warning(f"No awaiting order with id = {order_id}")
        raise NoOrderException(order_id=order_id, message=resp_fail1)
    elif order.status != OrderStatus.received:
        logger.warning(f"Order with id = {order_id} has wrong status")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": resp_fail2})
    else:
        asyncio.create_task(process_order(order))
        logger.info(f"Processing order with id = {order_id}")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": resp_success, "orderId": order.id})


@app.post('/clients/add', response_model_exclude_unset=True, response_model=None, tags=[Tags.clients])
async def add_client_without_task(client_name1: Annotated[str, Query(min_length=3, max_length=30, pattern="^.+$", title="Main name", description="Obligatory part of the name")],
                                client_name2: Annotated[str | None, Query(min_length=3, max_length=30, pattern="^.+$", deprecated=True)] = None,
                                passwords: Annotated[list[str] | None, Query(alias="List of parts of password :)")] = None) -> Response | ClientOut:
    async with orders_lock:
        full_name = client_name1 if client_name2 is None else client_name1 + client_name2
        client = memory_package.get_client_by_name(full_name)
        if client is None:
            if passwords is None:
                password = "123"
            else:
                password = "".join(passwords)
            memory_package.add_client(Client(name=full_name, password=password))
            logger.info(f"Created new client without orders with name {full_name}")
            return ClientOut(name=full_name)
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Name used"})


@app.get('/clients/', response_model=list[ClientOut], tags=[Tags.clients])
async def get_clients(count: Annotated[int | None, Query(gt=0)] = None):
    return memory_package.get_clientsDb(count)


@app.post('/orders/{client_name}', tags=[Tags.order_create])
async def create_order(client_name: str, orderDto: Annotated[OrderDTO | None, Body()] = None):
    if orderDto is None:
        logger.warning('No order')
        raise NoOrderException()
    async with orders_lock:
        new_order = map_orderDto_to_Order(orderDto, client_name)
        client = next((client for client in memory_package.get_clientsDb() if client.name == client_name), None)
        if client is None:
            memory_package.add_client(Client(name=client_name, password="123", orders=[new_order]))
            logger.info('Created new client')
        else:
            client.orders.add(new_order)
            logger.info('Added new order to the existing client')
        memory_package.add_order(new_order)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})


@app.get('/orders/get/all', response_model=list[Order], status_code=status.HTTP_202_ACCEPTED, tags=[Tags.order_get])
async def get_orders():
    logger.info('Return all orders list ')
    return_dict = await memory_package.get_all_orders_as_dict()
    return return_dict


@app.get('/orders/get/headers', tags=[Tags.order_get])
async def get_orders_counts_from_header(clients_names: Annotated[str | None, Header()] = None):
    async with orders_lock:
        if clients_names:
            clients_names_list = clients_names.split(',')
        else:
            clients_names_list = []
        clients = [client for client in memory_package.get_clientsDb() if client.name in clients_names_list]
    if len(clients) > 0:
        results = []
        for client in clients:
            logger.info(f"Return user''s {client.name} orders count from header")
            async with orders_lock:
                results.append(len(client.orders))
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "clients_orders_count": results})
    else:
        logger.warning(f"No user with names given in header")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect header values"})


@app.get('/orders/get/{client_name}', tags=[Tags.order_get])
async def get_orders_by_client(client_name: str):
    async with orders_lock:
        client = next((client for client in memory_package.get_clientsDb() if client.name == client_name), None)
    if client is not None:
        logger.info(f"Return user''s {client_name} orders list")
        async with orders_lock:
            return_dict = [order.dict() for order in client.orders]
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orders": return_dict})
    else:
        logger.warning(f"No user with name: {client_name}")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect username"})


@app.get('/orders/get/status/{status_name}', tags=[Tags.order_get])
async def get_orders_by_status(status_name: OrderStatus):
    async with orders_lock:
        logger.info(f"Return orders with status = {status_name.value} list")
        return_dict = [order.dict() for order in memory_package.get_ordersDb() if order.status == status_name]
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orders": return_dict})


@app.delete('/orders/remove', tags=[Tags.order_delete], response_description="Number of removed orders")
async def delete_orders_of_ids(first: int = 0, last: int = sys.maxsize):
    if last < first:
        logger.warning(f"Tried to remove order with greater first id then last id")
        return JSONResponse(status_code=status.HTTP_412_PRECONDITION_FAILED,
                            content={"message": "First id greater than last id"})
    orders_to_remove = []
    async with orders_lock:
        for order in memory_package.get_ordersDb():
            if first <= order.id <= last:
                orders_to_remove.append(order)
        for order in orders_to_remove:
            memory_package.remove_order(order)
            logger.info(f"Removing order with id {order.id}")
            client = next((client for client in memory_package.get_clientsDb() if client.name == order.client_name), None)
            client.orders.remove(order)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "removed_count": len(orders_to_remove)})


@app.delete('/orders/{order_id}', tags=[Tags.order_delete])
async def delete_order(order_id: int):
    async with orders_lock:
        removed_order = next((order for order in memory_package.get_ordersDb() if order.id == order_id), None)
        if removed_order:
            new_ordersDb = [order for order in memory_package.get_ordersDb() if order.id != order_id]
            memory_package.set_new_ordersDb(new_ordersDb)
            logger.info(f"Removing order with id {order_id}")
            client = next((client for client in memory_package.get_clientsDb() if client.name == removed_order.client_name), None)
            client.orders.remove(removed_order)
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)


@app.get('/', tags=[Tags.order_get])
def send_app_info(ads_id: Annotated[str | None, Cookie()]):
    """
    Get info if app works and how many tasks are currently saved

    **ads_id**: cookie data simulation
    """
    if ads_id is not None:
        logger.info('We have cookie value: ' + ads_id)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "ads_id": ads_id, "tasks_count": len(memory_package.get_ordersDb())})


@app.post('/orders/swap/{order_id}', tags=[Tags.order_update])
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
        swapped_order = next((order for order in memory_package.get_ordersDb() if order.id == order_id), None)
        if swapped_order:
            logger.info(f"Swapping client of order with id {order_id}")
            old_client = next((client for client in memory_package.get_clientsDb() if client.name == swapped_order.client_name), None)
            old_client.orders.remove(swapped_order)
            swapped_order.client_name = client_name
            if client_name is not None:
                new_client = next((client for client in memory_package.get_clientsDb() if client.name == swapped_order.client_name), None)
                if new_client is None:
                    memory_package.add_client(Client(name=client_name, orders=[swapped_order]))
                    logger.info('Created new client')
                else:
                    new_client.orders.add(swapped_order)
                    logger.info('Added new order to the existing client')
            return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)


@app.post("/login/", response_model=None, tags=[Tags.clients])
async def login(name: Annotated[str, Form()], password: Annotated[str, Form()]) -> ClientOut | JSONResponse:
    client = memory_package.get_client_by_name(name)
    if client and client.password == password:
        return ClientOut(**client.dict())
    elif client and client.password != password:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Wrong password"})
    else:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong name"})


@app.post("/login/set_photo", response_model=None, tags=[Tags.clients], summary="Set photo for client",
          description="With correct login parameters and file, simulates uploading photo")
async def login_and_set_photo(name: Annotated[str, Form()], password: Annotated[str, Form()], file: UploadFile) -> JSONResponse:
    if file is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong photo"})
    response = await login(name, password)
    if isinstance(response, JSONResponse):
        return response
    else:
        content = file.file.read()
        client = next((client for client in memory_package.get_clientsDb() if client.name == name), None)
        client.photo = content
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})


def get_next_order_id():
    return 0 if len(memory_package.get_ordersDb()) == 0 else max(memory_package.get_ordersDb(), key=lambda order: order.id).id + 1


def map_orderDto_to_Order(orderDto: OrderDTO, client_name: str):
    return Order(id=get_next_order_id(), description=orderDto.description,
                 time=orderDto.time, client_name=client_name, creation_date=orderDto.timestamp.isoformat())

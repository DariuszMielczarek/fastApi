import asyncio
import base64
import sys
from typing import Annotated
from fastapi import Body, FastAPI, Query, Path, Cookie, Header, Form, UploadFile, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import memory_package
from blocking_list import BlockingList
from exceptions import NoOrderException
from mapper import map_orderDto_to_Order
from memory_package import logger, orders_lock, Client, ClientOut, clientsDb, get_clients_by_ids, \
    get_orders_by_client_id, remove_client, open_dbs, close_dbs, get_clientsDb, get_ordersDb
from orders_management_package import OrderDTO
from order_package import Order, OrderStatus
from orders_management_package.process_order import process_order
from tags import Tags


async def global_dependency_verify_key_common(key: Annotated[str | None, Header()] = None):
    if key == "yek":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key from global dependency")


def dependency_with_yield():
    try:
        open_dbs()
        yield get_clientsDb(), get_ordersDb()
    except Exception:
        raise
    finally:
        close_dbs()
        open_dbs()


app = FastAPI(dependencies=[Depends(global_dependency_verify_key_common), Depends(dependency_with_yield)])


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
    async with orders_lock:
        order = memory_package.get_order_by_id(order_id)
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
                                passwords: Annotated[list[str] | None, Query(alias="passes")] = None) -> Response | ClientOut:
    full_name = client_name1 if client_name2 is None else client_name1 + client_name2
    async with orders_lock:
        client = memory_package.get_client_by_name(full_name)
        if client is None:
            password = "".join(passwords) if passwords else "123"
            memory_package.add_client(Client(name=full_name, password=password))
            logger.info(f"Created new client without orders with name {full_name}")
            return ClientOut(name=full_name)
        else:
            logger.warning('Client already exists')
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": "Name used"})


@app.get('/clients/', response_model=list[ClientOut], tags=[Tags.clients])
async def get_clients(count: Annotated[int | None, Query(gt=0)] = None):
    return memory_package.get_clientsDb(count)


@app.post('/orders/{client_id}', tags=[Tags.order_create])
async def create_order(client_id: int, orderDto: Annotated[OrderDTO | None, Body()] = None):
    if orderDto is None:
        logger.warning('No order')
        raise NoOrderException()
    async with orders_lock:
        new_order = map_orderDto_to_Order(orderDto, client_id)
        client = get_clients_by_ids([client_id])
        if len(client) == 0:
            memory_package.add_client(Client(name="New client" + str(client_id), password="123", orders=[new_order]))
            logger.info('Created new client')
        else:
            memory_package.add_order_to_client(new_order, client[0])
            logger.info('Added new order to the existing client')
        memory_package.add_order(new_order)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})


@app.get('/orders/get/all', response_model=list[Order], status_code=status.HTTP_202_ACCEPTED, tags=[Tags.order_get])
async def get_orders():
    logger.info('Return all orders list ')
    return_dict = await memory_package.get_all_orders_as_dict()
    return return_dict


@app.get('/orders/get/headers', tags=[Tags.order_get])
async def get_orders_counts_from_header(clients_ids: Annotated[str | None, Header()] = None):
    clients_ids_list = clients_ids.split(',') if clients_ids else []
    clients_ids_int_list = []
    for client_id in clients_ids_list:
        try:
            clients_ids_int_list.append(int(client_id))
        except ValueError:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect header values"})
    clients_ids_int_list = [int(client_id) for client_id in clients_ids_list]
    async with orders_lock:
        clients = get_clients_by_ids(clients_ids_int_list)
    if len(clients) > 0:
        results = []
        for client in clients:
            logger.info(f"Return user''s {client.name} orders count from header")
            async with orders_lock:
                results.append(len(client.orders))
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "clients_orders_count": results})
    else:
        logger.warning(f"No user with ids given in header")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect header values"})


@app.get('/orders/get/{client_id}', tags=[Tags.order_get])
async def get_orders_by_client(client_id: int):
    async with orders_lock:
        orders = get_orders_by_client_id(client_id)
    if orders is not None:
        logger.info(f"Return user''s {client_id} orders list")
        return JSONResponse(status_code=status.HTTP_200_OK,
                            content={"message": "Success", "orders": [jsonable_encoder(order.model_dump()) for order in orders]})
    else:
        logger.warning(f"No user with id: {client_id}")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect id"})


@app.get('/orders/get/status/{status_name}', tags=[Tags.order_get])
async def get_orders_by_status(status_name: OrderStatus):
    async with orders_lock:
        logger.info(f"Return orders with status = {status_name.value} list")
        return_dict = [jsonable_encoder(order.model_dump()) for order in memory_package.get_ordersDb() if order.status == status_name]
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orders": return_dict})


async def delete_of_ids_common_parameters(first: int = 0, last: int = sys.maxsize):
    return {"first": first, "last": last}


CommonDependencyAnnotation = Annotated[dict, Depends(delete_of_ids_common_parameters)]


@app.delete('/orders/remove', tags=[Tags.order_delete], response_description="Number of removed orders")
async def delete_orders_of_ids(commons: CommonDependencyAnnotation):
    first = commons['first']
    last = commons['last']
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
            client = next((client for client in memory_package.get_clientsDb() if client.id == order.client_id), None)
            client.orders.remove(order)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "removed_count": len(orders_to_remove)})


@app.delete('/clients/remove', tags=[Tags.order_delete], response_description="Number of removed clients")
async def delete_clients_of_ids(commons: CommonDependencyAnnotation):
    first = commons['first']
    last = commons['last']
    if last < first:
        logger.warning(f"Tried to remove order with greater first id then last id")
        return JSONResponse(status_code=status.HTTP_412_PRECONDITION_FAILED,
                            content={"message": "First id greater than last id"})
    clients_to_remove = []
    async with orders_lock:
        for client in memory_package.get_clientsDb():
            if first <= client.id <= last:
                clients_to_remove.append(client)
        for client in clients_to_remove:
            for order in client.orders:
                memory_package.remove_order(order)
                logger.info(f"Removing order with id {order.id}")
            remove_client(client)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "removed_count": len(clients_to_remove)})


@app.delete('/orders/{order_id}', tags=[Tags.order_delete])
async def delete_order(order_id: int):
    async with orders_lock:
        removed_order = next((order for order in memory_package.get_ordersDb() if order.id == order_id), None)
        if removed_order:
            new_ordersDb = [order for order in memory_package.get_ordersDb() if order.id != order_id]
            new_ordersDb = BlockingList(new_ordersDb)
            memory_package.set_new_ordersDb(new_ordersDb)
            logger.info(f"Removing order with id {order_id}")
            client = next((client for client in memory_package.get_clientsDb() if client.id == removed_order.client_id), None)
            client.orders.remove(removed_order)
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)


def query_parameter_extractor(q: str | None = None):
    return q


def query_or_cookie_extractor(q: Annotated[str, Depends(query_parameter_extractor)],
                              ads_id: Annotated[str | None, Cookie()] = None):
    return q if q else ads_id


@app.get('/', tags=[Tags.order_get])
def send_app_info(query_or_ads_id: Annotated[str, Depends(query_or_cookie_extractor)] = None):
    """
    Get info if app works and how many tasks are currently saved

    **query_or_ads_id**: query data or, if empty, cookie data
    """
    if query_or_ads_id is not None:
        logger.info('App info function query/cookies value: ' + query_or_ads_id)
    else:
        logger.info('App info function called without query/cookies value')
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "query_or_ads_id": query_or_ads_id, "tasks_count": len(memory_package.get_ordersDb())})


@app.post('/orders/swap/{order_id}', tags=[Tags.order_update])
async def swap_orders_client(order_id: int, client_id: Annotated[int | None, Query(openapi_examples={
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
            old_client = next((client for client in memory_package.get_clientsDb() if client.id == swapped_order.client_id), None)
            old_client.orders.remove(swapped_order)
            swapped_order.client_id = client_id
            if client_id is not None:
                new_client = next((client for client in memory_package.get_clientsDb() if client.id == swapped_order.client_id), None)
                if new_client is None:
                    memory_package.add_client(Client(name="New client"+str(client_id), password="123", orders=[swapped_order]))
                    logger.info('Created new client')
                else:
                    new_client.orders.append(swapped_order)
                    logger.info('Added new order to the existing client')
            return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)


class CommonQueryParamsClass:
    def __init__(self, name: Annotated[str, Form()], password: Annotated[str, Form()]):
        self.name = name
        self.password = password


@app.post("/login/", response_model=None, tags=[Tags.clients])
async def login(commons: Annotated[CommonQueryParamsClass, Depends()]) -> ClientOut | JSONResponse:
    client = memory_package.get_client_by_name(commons.name)
    if client and client.password == commons.password:
        return ClientOut(**client.model_dump())
    elif client and client.password != commons.password:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Wrong password"})
    else:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong name"})


@app.post("/login/set_photo", response_model=None, tags=[Tags.clients], summary="Set photo for client",
          description="With correct login parameters and file, simulates uploading photo")
async def login_and_set_photo(commons: Annotated[CommonQueryParamsClass, Depends()],
                              file: UploadFile | None = None) -> JSONResponse | ClientOut:
    if file is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Wrong photo"})
    response = await login(commons)
    if isinstance(response, JSONResponse):
        return response
    else:
        content = file.file.read()
        content = base64.b64encode(content).decode('utf-8')
        client = memory_package.get_client_by_name(commons.name)
        client.photo = content
        return ClientOut(**client.model_dump())


@app.put("/clients/update/all/{client_name}", response_model=None, tags=[Tags.clients])
async def change_client_data(client_name: Annotated[str, Path()],
                             name: Annotated[str | None, Query()] = None,
                             password: Annotated[str | None, Query()] = None) -> JSONResponse | ClientOut:
    client = memory_package.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    updated_client = Client(**client.model_dump())
    updated_client.name = name if name is not None else updated_client.name
    updated_client.password = password if password is not None else updated_client.password
    for i, client in enumerate(clientsDb):
        if client.name == client_name:
            clientsDb[i] = updated_client
    return ClientOut(**updated_client.model_dump())


async def verify_key_common(verification_key: Annotated[str, Header()]):
    if verification_key != "key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")
    return verification_key


@app.patch("/clients/update/password/{client_name}",
           response_model=None, tags=[Tags.clients], dependencies=[Depends(verify_key_common)])
async def change_client_password(client_name: Annotated[str, Path()],
                                 password: Annotated[str, Query()]) -> JSONResponse | ClientOut:
    client = memory_package.get_client_by_name(client_name)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Wrong name"})
    client.password = password if password is not None else client.password
    return ClientOut(**client.model_dump())


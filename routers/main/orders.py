import asyncio
from typing import Annotated
from fastapi import APIRouter, Query, Depends, Header, Body, Path, HTTPException, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from starlette import status
from starlette.responses import JSONResponse, Response
import memory_package
from background_tasks import send_notification_simulator
from blocking_list import BlockingList
from client_management_package import hash_password
from dependencies_package.main.dependencies import CommonDependencyAnnotation, oauth2_scheme, get_current_client
from exceptions import NoOrderException
from mapper import map_orderDto_to_Order
from memory_package import orders_lock, Client, logger, get_orders_by_client_id, get_clients_by_ids, ClientOut, \
    get_client_by_id
from order_package import OrderStatus, Order
from orders_management_package import OrderDTO, process_order
from tags import Tags

order_router = APIRouter(prefix="/orders")


@order_router.post('/swap/{order_id}', tags=[Tags.order_update])
async def swap_orders_client(background_tasks: BackgroundTasks,
        order_id: int, client_id: Annotated[int | None, Query(openapi_examples={
                "normal": {
                    "summary": "Normal example",
                    "description": "A **normal** item works correctly.",
                    "value": "0"
                },
                "converted": {
                    "summary": "Empty example",
                    "description": "**Empty** ***None*** works correctly",
                    "value": "None"
                }
            })] = None):
    async with orders_lock:
        swapped_order = next((order for order in memory_package.get_orders_db() if order.id == order_id), None)
        if swapped_order:
            logger.info(f"Swapping client of order with id {order_id}")
            old_client = get_client_by_id(swapped_order.client_id)
            old_client.orders.remove(swapped_order)
            swapped_order.client_id = client_id
            if client_id is not None:
                new_client = next((client for client in memory_package.get_clients_db() if client.id == swapped_order.client_id), None)
                if new_client is None:
                    memory_package.add_client(Client(name="New client"+str(client_id), password=hash_password("123"), orders=[swapped_order]))
                    background_tasks.add_task(send_notification_simulator, name="New client" + str(client_id))
                    logger.info('Created new client')
                else:
                    new_client.orders.append(swapped_order)
                    logger.info('Added new order to the existing client')
            return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)


@order_router.delete('/remove', tags=[Tags.order_delete], response_description="Number of removed orders")
async def delete_orders_of_ids(commons: CommonDependencyAnnotation):
    first = commons['first']
    last = commons['last']
    if last < first:
        logger.warning(f"Tried to remove order with greater first id then last id")
        return JSONResponse(status_code=status.HTTP_412_PRECONDITION_FAILED,
                            content={"message": "First id greater than last id"})
    orders_to_remove = []
    async with orders_lock:
        for order in memory_package.get_orders_db():
            if first <= order.id <= last:
                orders_to_remove.append(order)
        for order in orders_to_remove:
            memory_package.remove_order(order)
            logger.info(f"Removing order with id {order.id}")
            client = next((client for client in memory_package.get_clients_db() if client.id == order.client_id), None)
            client.orders.remove(order)
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "removed_count": len(orders_to_remove)})


@order_router.get('/get/status/{status_name}', tags=[Tags.order_get])
async def get_orders_by_status(status_name: OrderStatus):
    async with (orders_lock):
        logger.info(f"Return orders with status = {status_name.value} list")
        return_dict =[jsonable_encoder(order.model_dump())
                      for order in memory_package.get_orders_db() if order.status == status_name]
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orders": return_dict})


@order_router.get('/get/headers', tags=[Tags.order_get])
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


@order_router.get('/get/all', response_model=list[Order], status_code=status.HTTP_202_ACCEPTED, tags=[Tags.order_get])
async def get_orders(token: Annotated[str, Depends(oauth2_scheme)]):
    logger.info('Return all orders list ')
    return_dict = await memory_package.get_all_orders_as_dict()
    return return_dict


@order_router.get('/get/current', tags=[Tags.order_get])
async def get_orders_by_current_client(current_user: Annotated[ClientOut, Depends(get_current_client)]):
    return current_user.orders


@order_router.get('/get/{client_id}', tags=[Tags.order_get])
async def get_orders_by_client(client_id: int):
    async with orders_lock:
        orders = get_orders_by_client_id(client_id)
    if orders is not None:
        logger.info(f"Return user''s {client_id} orders list")
        return JSONResponse(status_code=status.HTTP_200_OK,
                            content={"message": "Success",
                                     "orders": [jsonable_encoder(order.model_dump()) for order in orders]})
    else:
        logger.warning(f"No user with id: {client_id}")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect id"})


@order_router.post('/process/{order_id}', tags=[Tags.order_process])
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


@order_router.post('/process', tags=[Tags.order_process], deprecated=True)
async def process_next_order() -> JSONResponse:
    order = await memory_package.get_first_order_with_status(OrderStatus.received)
    if order is None:
        logger.warning("No awaiting order")
        raise NoOrderException(message="No awaiting order")
    else:
        asyncio.create_task(process_order(order))
        logger.info("Processing order")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orderId": order.id})


@order_router.post('/{client_id}', tags=[Tags.order_create])
async def create_order(background_tasks: BackgroundTasks, client_id: int, orderDto: Annotated[OrderDTO | None, Body()] = None):
    if orderDto is None:
        logger.warning('No order')
        raise NoOrderException(order_id=client_id)
    async with orders_lock:
        client = get_client_by_id(client_id)
        if not client:
            new_order = map_orderDto_to_Order(orderDto)
            assigned_client_id = memory_package.add_client(
                Client(name="New client" + str(client_id), password=hash_password("123")))
            new_order.client_id = assigned_client_id
            memory_package.add_order_to_client(new_order, get_client_by_id(assigned_client_id))
            background_tasks.add_task(send_notification_simulator, name="New client" + str(client_id))
            logger.info('Created new client')
        else:
            new_order = map_orderDto_to_Order(orderDto, client_id)
            memory_package.add_order_to_client(new_order, client)
            logger.info('Added new order to the existing client')
        memory_package.add_order(new_order)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})


@order_router.delete('/{order_id}', tags=[Tags.order_delete])
async def delete_order(order_id: int):
    async with orders_lock:
        removed_order = next((order for order in memory_package.get_orders_db() if order.id == order_id), None)
        if removed_order:
            new_ordersDb = [order for order in memory_package.get_orders_db() if order.id != order_id]
            new_ordersDb = BlockingList(new_ordersDb)
            memory_package.set_new_orders_db(new_ordersDb)
            logger.info(f"Removing order with id {order_id}")
            client = next((client for client in memory_package.get_clients_db() if client.id == removed_order.client_id), None)
            client.orders.remove(removed_order)
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)

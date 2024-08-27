import asyncio
from typing import Annotated
from fastapi import APIRouter, Query, Depends, Header, Body, Path, HTTPException, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from starlette import status
from starlette.responses import JSONResponse, Response
import memory_package
from app.main.background_tasks import send_notification_simulator
from client_package.client import ClientOut
from memory_package.blocking_list import BlockingList
from client_management_package import hash_password
from dependencies_package.main.dependencies import CommonDependencyAnnotation, oauth2_scheme, get_current_client
from app.main.exceptions import NoOrderException
from orders_management_package.mapper import map_order_dto_to_order
from memory_package import orders_lock, logger
from order_package import OrderStatus, Order
from orders_management_package import OrderDTO, process_order
from app.main.tags import Tags

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
        })] = None):   # noqa: E501
    async with orders_lock:
        swapped_order = memory_package.db.get_order_by_id(order_id)
        if swapped_order:
            logger.info(f"Swapping client of order with id {order_id}")
            old_client = memory_package.db.get_client_by_id(swapped_order.client_id)
            memory_package.db.remove_order_from_client(old_client, swapped_order)
            if client_id is not None:
                new_client = memory_package.db.get_client_by_id(client_id)
                if new_client is None:
                    client_id = memory_package.db.add_client(name="New client" + str(client_id),
                                                             password=hash_password("123"))
                    memory_package.db.add_order_to_client(swapped_order, memory_package.db.get_client_by_id(client_id))
                    background_tasks.add_task(send_notification_simulator, name="New client" + str(client_id))
                    logger.info('Created new client')
                else:
                    memory_package.db.add_order_to_client(swapped_order, new_client)
                    logger.info('Added new order to the existing client')
            memory_package.db.change_order_owner(client_id, swapped_order.id)
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
        for order in memory_package.db.get_orders_db():
            if first <= order.id <= last:
                orders_to_remove.append(order)
        for order in orders_to_remove:
            memory_package.db.remove_order(order)
            logger.info(f"Removing order with id {order.id}")
            memory_package.db.remove_order_from_client(memory_package.db.get_client_by_id(order.client_id), order)
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"message": "Success", "removed_count": len(orders_to_remove)})


@order_router.get('/get/status/{status_name}', tags=[Tags.order_get])
async def get_orders_by_status(status_name: OrderStatus):
    async with (orders_lock):
        logger.info(f"Return orders with status = {status_name.value} list")
        return_dict = [jsonable_encoder(Order.model_validate(order).model_dump())
                       for order in memory_package.db.get_orders_db() if order.status == status_name]
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
        clients = memory_package.db.get_clients_by_ids(clients_ids_int_list)
    if len(clients) > 0:
        results = []
        for client in clients:
            logger.info(f"Return user''s {client.name} orders count from header")
            async with orders_lock:
                results.append(len(memory_package.db.get_orders_by_client_name(client.name)))
        return JSONResponse(status_code=status.HTTP_200_OK,
                            content={"message": "Success", "clients_orders_count": results})
    else:
        logger.warning(f"No user with ids given in header")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect header values"})


@order_router.get('/get/all', response_model=list[Order], status_code=status.HTTP_202_ACCEPTED, tags=[Tags.order_get])
async def get_orders(_token: Annotated[str, Depends(oauth2_scheme)]):
    logger.info('Return all orders list ')
    return_dict = await memory_package.db.get_all_orders_as_dict()
    return return_dict


@order_router.get('/get/current', tags=[Tags.order_get])
async def get_orders_by_current_client(current_user: Annotated[ClientOut | memory_package.Client, Depends(get_current_client)]):  # noqa: E501
    return await get_orders_by_client(memory_package.db.get_client_id_from_client_by_name(current_user.name))


@order_router.get('/get/{client_id}', tags=[Tags.order_get])
async def get_orders_by_client(client_id: int):
    async with orders_lock:
        orders = memory_package.db.get_orders_by_client_id(client_id)
    if orders is not None:
        logger.info(f"Return user''s {client_id} orders list")
        return JSONResponse(status_code=status.HTTP_200_OK,
                            content={"message": "Success",
                                     "orders": [jsonable_encoder(Order.model_validate(order).model_dump()) for order in orders]})  # noqa: E501
    else:
        logger.warning(f"No user with id: {client_id}")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Incorrect id"})


@order_router.post('/process/{order_id}', tags=[Tags.order_process])
async def process_order_of_id(order_id: Annotated[int, Path(title="Order to process", ge=0)],
                              resp_fail1: Annotated[str | None, Body()] = "No such order",
                              resp_fail2: Annotated[str | None, Body()] = "Order does not await for process",
                              resp_success: str | None = "Success") -> Response:
    async with orders_lock:
        order = memory_package.db.get_order_by_id(order_id)
    if order is None:
        logger.warning(f"No awaiting order with id = {order_id}")
        raise NoOrderException(order_id=order_id, message=resp_fail1)
    elif order.status != OrderStatus.received:
        logger.warning(f"Order with id = {order_id} has wrong status")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": resp_fail2})
    else:
        asyncio.create_task(process_order(order))  # noqa
        logger.info(f"Processing order with id = {order_id}")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": resp_success, "orderId": order.id})


@order_router.post('/process', tags=[Tags.order_process], deprecated=True)
async def process_next_order() -> JSONResponse:
    order = await memory_package.db.get_first_order_with_status(OrderStatus.received)
    if order is None:
        logger.warning("No awaiting order")
        raise NoOrderException(message="No awaiting order")
    else:
        asyncio.create_task(process_order(order))  # noqa
        logger.info("Processing order")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success", "orderId": order.id})


@order_router.post('/{client_id}', tags=[Tags.order_create])
async def create_order(background_tasks: BackgroundTasks, client_id: int,
                       order_dto: Annotated[OrderDTO | None, Body()] = None):
    if order_dto is None:
        logger.warning('No order')
        raise NoOrderException(order_id=client_id)
    async with orders_lock:
        client = memory_package.db.get_client_by_id(client_id)
        if not client:
            new_order = map_order_dto_to_order(order_dto)
            assigned_client_id = memory_package.db.add_client(
                name="New client" + str(client_id), password=hash_password("123"))
            new_order.client_id = assigned_client_id
            memory_package.db.add_order_to_client(new_order, memory_package.db.get_client_by_id(assigned_client_id))
            background_tasks.add_task(send_notification_simulator, name="New client" + str(client_id))
            logger.info('Created new client')
        else:
            new_order = map_order_dto_to_order(order_dto, client_id)
            memory_package.db.add_order_to_client(new_order, client)
            logger.info('Added new order to the existing client')
        memory_package.db.add_order(new_order)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Success"})


@order_router.delete('/{order_id}', tags=[Tags.order_delete])
async def delete_order(order_id: int):
    async with orders_lock:
        removed_order = memory_package.db.get_order_by_id(order_id)
        if removed_order:
            new_orders_db = [order for order in memory_package.db.get_orders_db() if order.id != order_id]
            new_orders_db = BlockingList(new_orders_db)
            memory_package.db.set_new_orders_db(new_orders_db)
            logger.info(f"Removing order with id {order_id}")
            client = memory_package.db.get_client_by_id(removed_order.client_id)
            memory_package.db.remove_order_from_client(client, removed_order)
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Success"})
        else:
            logger.warning(f"No order with id {order_id}")
            raise NoOrderException(order_id=order_id)

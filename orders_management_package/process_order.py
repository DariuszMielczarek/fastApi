from asyncio import sleep, create_task

from memory_package import orders_lock, logger, clients_db
from order_package import Order, OrderStatus


async def process_order(order: Order):
    task = create_task(process_simulator(order))
    async with orders_lock:
        order.status = OrderStatus.in_progress
        replace_order_in_client_object(order)
    await task
    logger.info("Finished processing order")
    async with orders_lock:
        order.status = OrderStatus.complete
        replace_order_in_client_object(order)


async def process_simulator(order: Order):
    await sleep(order.time)


def replace_order_in_client_object(order: Order):
    for client in clients_db:
        if client.id == order.client_id:
            for i, c_order in enumerate(client.orders):
                if c_order.id == order.id:
                    client.orders[i] = order


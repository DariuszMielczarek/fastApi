from asyncio import sleep, create_task

from memory_package import orders_lock, logger, clientsDb
from order_package import Order, OrderStatus


async def process_order(order: Order):
    task = create_task(process_simulator(order))
    async with orders_lock:
        order.status = OrderStatus.in_progress
        for client in clientsDb:
            if client.name == order.client_name:
                for i, c_order in enumerate(client.orders):
                    if c_order.id == order.id:
                        client.orders[i] = order
    await task
    logger.info("Finished processing order")
    async with orders_lock:
        order.status = OrderStatus.complete
        for client in clientsDb:
            if client.name == order.client_name:
                for i, c_order in enumerate(client.orders):
                    if c_order.id == order.id:
                        client.orders[i] = order


async def process_simulator(order: Order):
    await sleep(order.time)


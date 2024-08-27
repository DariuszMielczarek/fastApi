from asyncio import sleep, create_task

import memory_package
from memory_package import orders_lock, logger
from order_package import Order, OrderStatus


async def process_order(order: Order):
    task = create_task(process_simulator(order))
    async with orders_lock:
        order.status = OrderStatus.in_progress
        memory_package.db.replace_order_in_client_object(order)
    await task
    logger.info("Finished processing order")
    async with orders_lock:
        order.status = OrderStatus.complete
        memory_package.db.replace_order_in_client_object(order)


async def process_simulator(order: Order):
    await sleep(order.time)

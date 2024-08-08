from asyncio import sleep, create_task

from memory_package import orders_lock, logger
from orders_management_package import OrderStatus, Order


async def process_order(order: Order):
    task = create_task(process_simulator(order))
    async with orders_lock:
        order.status = OrderStatus.in_progress
    await task
    logger.info("Finished processing order")
    async with orders_lock:
        order.status = OrderStatus.complete


async def process_simulator(order: Order):
    await sleep(order.time)


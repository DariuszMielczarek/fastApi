from asyncio import sleep

from memory_package import logger


async def send_notification_simulator(name: str):
    await sleep(0.01)
    logger.info(f"NOTIFICATION - ACCOUNT WITH NAME {name}")

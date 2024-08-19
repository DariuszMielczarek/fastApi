import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
orders_lock = asyncio.Lock()
calls_count = 0
calls_lock = asyncio.Lock()


async def increment_calls_count():
    global calls_count
    async with calls_lock:
        calls_count += 1
        return calls_count


def set_calls_count(value: int):
    global calls_count
    calls_count = value

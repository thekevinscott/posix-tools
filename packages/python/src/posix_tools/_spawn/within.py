import asyncio
from collections.abc import Awaitable


async def within(seconds: float, awaitable: Awaitable[object]) -> bool:
    try:
        async with asyncio.timeout(seconds):
            await awaitable
    except TimeoutError:
        return False
    return True

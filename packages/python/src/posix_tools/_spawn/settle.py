import asyncio
from collections.abc import Awaitable


async def settle[T](awaitable: Awaitable[T]) -> T:
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError from task.exception()
    return task.result()

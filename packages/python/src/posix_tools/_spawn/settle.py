import asyncio
from collections.abc import Awaitable


async def settle[T](coro: Awaitable[T]) -> T:
    """Finish cleanup through repeated cancels, then preserve the caller's cancellation."""
    task = asyncio.ensure_future(coro)
    cancelled = False
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError from task.exception()
    return task.result()

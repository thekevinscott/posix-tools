import asyncio
from collections.abc import Sequence
from typing import Any

from posix_tools._spawn.group_alive import group_alive

POLL = 0.01


async def ended(
    process: asyncio.subprocess.Process, waiting: Sequence[asyncio.Future[Any]]
) -> None:
    # process.wait() also waits for every holder of the pipes to close them.
    while process.returncode is None:
        await asyncio.sleep(POLL)
    await asyncio.gather(*map(asyncio.shield, waiting), return_exceptions=True)
    while group_alive(process.pid):
        await asyncio.sleep(POLL)

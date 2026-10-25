import asyncio
from collections.abc import Sequence
from typing import Any

from posix_tools._spawn.discard import discard
from posix_tools._spawn.ended import ended
from posix_tools._spawn.settle import settle
from posix_tools._spawn.stop import stop
from posix_tools._spawn.within import within


async def close(
    process: asyncio.subprocess.Process,
    drains: Sequence[asyncio.Future[Any]],
    *,
    signum: int,
    grace: float,
    linger: float,
) -> None:
    if process.stdin is not None:
        process.stdin.close()
    readers = [
        asyncio.ensure_future(discard(pipe))
        for pipe in (process.stdout, process.stderr)
        if pipe is not None
    ]
    waiting = (*drains, *readers)
    try:
        finished = False
        try:
            finished = linger > 0 and await within(linger, ended(process, waiting))
        finally:
            if not finished:
                await settle(stop(process, waiting, signum=signum, grace=grace))
    finally:
        for reader in readers:
            reader.cancel()
        await settle(asyncio.gather(*readers, return_exceptions=True))

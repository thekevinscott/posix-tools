import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import IO, Any

from posix_tools._spawn.abandon import abandon
from posix_tools._spawn.settle import settle
from posix_tools._spawn.stop import stop

type Stream = int | IO[Any] | None


@asynccontextmanager
async def spawn(
    program: str,
    *args: str,
    stdin: Stream = None,
    stdout: Stream = None,
    stderr: Stream = None,
) -> AsyncIterator[asyncio.subprocess.Process]:
    starting = asyncio.ensure_future(
        asyncio.create_subprocess_exec(
            program, *args, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True
        )
    )
    try:
        process = await asyncio.shield(starting)
    except asyncio.CancelledError:
        await settle(abandon(starting))
        raise
    try:
        yield process
    finally:
        await settle(stop(process))

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import IO, Any

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
        yield await asyncio.shield(starting)
    finally:
        stopping = asyncio.ensure_future(stop(starting))
        cancelled = False
        while not stopping.done():
            try:
                await asyncio.wait({stopping})
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError from stopping.exception()
        stopping.result()

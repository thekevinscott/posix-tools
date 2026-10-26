import asyncio
import os
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import IO, Any

from posix_tools._spawn.terminate import terminate

type Stream = int | IO[Any] | None

GRACE = 10
POLL = 0.01


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
        # A callback, not an await, so a second cancel can't skip it.
        starting.add_done_callback(terminate)
        raise
    try:
        yield process
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
            with suppress(TimeoutError):
                async with asyncio.timeout(GRACE):
                    while True:
                        # Raises ProcessLookupError once the group is gone.
                        os.killpg(process.pid, 0)
                        await asyncio.sleep(POLL)
            os.killpg(process.pid, signal.SIGKILL)
        await process.communicate()

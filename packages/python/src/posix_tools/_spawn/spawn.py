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
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
        deadline = asyncio.get_running_loop().time() + GRACE
        cancelled = False
        # Keep waiting through cancels: callers rely on nothing being left running.
        with suppress(ProcessLookupError):
            while True:
                with suppress(PermissionError):
                    os.killpg(process.pid, 0)
                if asyncio.get_running_loop().time() > deadline:
                    with suppress(PermissionError):
                        os.killpg(process.pid, signal.SIGKILL)
                    break
                try:
                    await asyncio.sleep(POLL)
                except asyncio.CancelledError:
                    cancelled = True
        await process.communicate()
        if cancelled:
            raise asyncio.CancelledError

import asyncio
import os
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from posix_tools._spawn.finish_sinks import finish_sinks
from posix_tools._spawn.reap import reap
from posix_tools._spawn.settle import settle
from posix_tools._spawn.start_drains import start_drains
from posix_tools._spawn.terminate import terminate
from posix_tools._spawn.types import Sink, Stream


@asynccontextmanager
async def spawn(
    program: str,
    *args: str,
    stdin: Stream = None,
    stdout: Sink | Stream = None,
    stderr: Sink | Stream = None,
    limit: int = 2**16,
) -> AsyncIterator[asyncio.subprocess.Process]:
    stdout_sink = stdout if callable(stdout) else None
    stderr_sink = stderr if callable(stderr) else None
    stdout_stream: Stream = asyncio.subprocess.PIPE if callable(stdout) else stdout
    stderr_stream: Stream = asyncio.subprocess.PIPE if callable(stderr) else stderr
    starting = asyncio.ensure_future(
        asyncio.create_subprocess_exec(
            program,
            *args,
            stdin=stdin,
            stdout=stdout_stream,
            stderr=stderr_stream,
            limit=limit,
            start_new_session=True,
        )
    )
    try:
        process = await asyncio.shield(starting)
    except asyncio.CancelledError:
        # A callback, not an await, so a second cancel can't skip it.
        starting.add_done_callback(terminate)
        raise
    errors: list[BaseException] = []
    drains = start_drains(process, (stdout_sink, stderr_sink), errors, asyncio.current_task())
    try:
        yield process
        # macOS raises EPERM, not ESRCH, when the group holds only zombies.
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
        if not drains:
            await process.communicate()
        else:
            await finish_sinks(process, drains)
    except BaseException:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        if drains:
            await settle(reap(process, drains))
        else:
            await settle(process.communicate())
        if errors:
            raise errors[0] from None
        raise

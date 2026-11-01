import asyncio
import os
import signal
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import IO, Any

from posix_tools._spawn.settle import settle
from posix_tools._spawn.terminate import terminate

type Stream = int | IO[Any] | None
type Sink = Callable[[bytes], object]

CHUNK_BYTES = 65536


async def _drain(reader: asyncio.StreamReader, sink: Sink | None) -> None:
    while chunk := await reader.read(CHUNK_BYTES):
        if sink is not None:
            sink(chunk)


async def _reap(
    process: asyncio.subprocess.Process,
    drains: dict[asyncio.StreamReader, asyncio.Task[None]],
) -> None:
    await asyncio.gather(*drains.values(), return_exceptions=True)
    for reader in (process.stdout, process.stderr):
        if reader is not None:
            await _drain(reader, None)
    await process.wait()


async def _finish_sinks(
    process: asyncio.subprocess.Process,
    drains: dict[asyncio.StreamReader, asyncio.Task[None]],
) -> None:
    if process.stdin is not None:
        process.stdin.close()
    for reader in (process.stdout, process.stderr):
        if reader is not None and reader not in drains:
            drains[reader] = asyncio.create_task(_drain(reader, None))
    exited = asyncio.create_task(process.wait())
    try:
        done, _ = await asyncio.wait(
            {exited, *drains.values()}, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in done:
            task.result()
    finally:
        if not exited.done():
            exited.cancel()


def _start_drains(
    process: asyncio.subprocess.Process,
    sinks: tuple[Sink | None, Sink | None],
    errors: list[BaseException],
    owner: asyncio.Task[object] | None,
) -> dict[asyncio.StreamReader, asyncio.Task[None]]:
    drains: dict[asyncio.StreamReader, asyncio.Task[None]] = {}

    def failed(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (error := task.exception()) is not None:
            errors.append(error)
            if owner is not None:
                owner.cancel()

    for reader, sink in zip((process.stdout, process.stderr), sinks, strict=True):
        if reader is not None and sink is not None:
            task = asyncio.create_task(_drain(reader, sink))
            task.add_done_callback(failed)
            drains[reader] = task
    return drains


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
    drains = _start_drains(process, (stdout_sink, stderr_sink), errors, asyncio.current_task())
    try:
        yield process
        if errors:
            raise errors[0]
        # macOS raises EPERM, not ESRCH, when the group holds only zombies.
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
        if not drains:
            await process.communicate()
        else:
            await _finish_sinks(process, drains)
    except BaseException:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        if drains:
            await settle(_reap(process, drains))
        else:
            await settle(process.communicate())
        if errors:
            raise errors[0] from None
        raise

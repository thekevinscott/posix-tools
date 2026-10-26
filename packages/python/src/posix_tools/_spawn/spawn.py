import asyncio
import os
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import IO, Any

type Stream = int | IO[Any] | None


@asynccontextmanager
async def spawn(
    program: str,
    *args: str,
    stdin: Stream = None,
    stdout: Stream = None,
    stderr: Stream = None,
) -> AsyncIterator[asyncio.subprocess.Process]:
    process = await asyncio.create_subprocess_exec(
        program, *args, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True
    )
    try:
        yield process
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        await process.communicate()

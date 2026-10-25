import asyncio
import signal
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import IO, Any

from posix_tools._spawn.close import close
from posix_tools._spawn.settle import settle

type Stream = int | IO[Any] | None


@asynccontextmanager
async def spawn(  # noqa: PLR0913
    program: str,
    *args: str,
    stdin: Stream = None,
    stdout: Stream = None,
    stderr: Stream = None,
    signum: int = signal.SIGTERM,
    grace: float = 10,
    linger: float = 0,
    drains: Sequence[asyncio.Future[Any]] = (),
) -> AsyncIterator[asyncio.subprocess.Process]:
    starting = asyncio.ensure_future(
        asyncio.create_subprocess_exec(
            program, *args, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True
        )
    )
    try:
        process = await asyncio.shield(starting)
    except asyncio.CancelledError:
        await settle(abandon(starting, signum=signum, grace=grace))
        raise
    clean = False
    try:
        yield process
        clean = True
    finally:
        await close(process, drains, signum=signum, grace=grace, linger=linger if clean else 0)


async def abandon(
    starting: asyncio.Future[asyncio.subprocess.Process], *, signum: int, grace: float
) -> None:
    try:
        process = await starting
    except Exception:
        return
    await close(process, (), signum=signum, grace=grace, linger=0)

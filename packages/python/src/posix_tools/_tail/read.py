import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from posix_tools._spawn.spawn import spawn
from posix_tools._tail.lines import Lines


@asynccontextmanager
async def read(path: Path, count: str) -> AsyncIterator[Lines]:
    """Print the file's last lines once.

    Opening the file here raises the usual `OSError`s, and tail exits at EOF.
    """
    with path.open("rb") as file:
        async with spawn(
            "tail",
            "-n",
            count,
            stdin=file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        ) as process:
            assert process.stdout is not None
            yield Lines(process.stdout)

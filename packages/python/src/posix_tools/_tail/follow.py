import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from posix_tools._spawn.spawn import spawn
from posix_tools._tail.lines import Lines


@asynccontextmanager
async def follow(path: Path, count: str) -> AsyncIterator[Lines]:
    """Follow the file by name, through rotation and absence."""
    async with spawn(
        "tail",
        "-F",
        "-n",
        count,
        "--",
        str(path),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        yield Lines(process.stdout)

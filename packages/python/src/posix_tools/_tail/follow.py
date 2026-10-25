import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from posix_tools._spawn.spawn import spawn
from posix_tools._tail.lines import Lines

# The wrapper holds our lifetime pipe as stdin. When we die, the pipe hits EOF and the wrapper
# kills tail. It lets go of stdout so a tail that exits on its own still ends the stream.
SCRIPT = 'tail -F -n "$1" -- "$2" & exec >/dev/null; read -r _; kill "$!"'


@asynccontextmanager
async def follow(path: Path, count: str) -> AsyncIterator[Lines]:
    """Follow the file by name, through rotation and absence."""
    lifetime, owner = os.pipe()
    try:
        async with spawn(
            "sh",
            "-c",
            SCRIPT,
            "sh",
            count,
            str(path),
            stdin=lifetime,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        ) as process:
            assert process.stdout is not None
            yield Lines(process.stdout)
    finally:
        os.close(owner)
        os.close(lifetime)

import asyncio
import os
import signal

import pytest

from posix_tools import spawn

IGNORE_TERM = "trap '' TERM; sleep 60 & echo ready; wait"


def gone(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def describe_spawn() -> None:
    async def it_kills_the_whole_group_on_exit() -> None:
        async with spawn("sh", "-c", "sleep 60 & sleep 60") as process:
            await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM
        assert gone(process.pid)

    async def it_kills_the_group_when_the_body_raises() -> None:
        with pytest.raises(ValueError, match="body"):
            async with spawn("sleep", "60") as process:
                raise ValueError("body")
        assert gone(process.pid)

    async def it_kills_a_program_whose_output_nobody_reads() -> None:
        async with asyncio.timeout(5):
            async with spawn("yes", stdout=asyncio.subprocess.PIPE) as process:
                await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM

    async def it_kills_a_group_that_ignores_sigterm() -> None:
        async with asyncio.timeout(15):
            async with spawn("sh", "-c", IGNORE_TERM, stdout=asyncio.subprocess.PIPE) as process:
                assert process.stdout is not None
                assert await process.stdout.readline() == b"ready\n"
        assert gone(process.pid)

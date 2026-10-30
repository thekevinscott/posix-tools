import asyncio
import os
import signal
import sys

import pytest

from posix_tools import spawn


async def gone(pgid: int) -> None:
    async with asyncio.timeout(5):
        while True:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return
            await asyncio.sleep(0.05)


def describe_spawn() -> None:
    async def it_kills_the_whole_group_on_exit() -> None:
        async with spawn("sh", "-c", "sleep 60 & sleep 60") as process:
            await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM
        await gone(process.pid)

    async def it_kills_the_group_when_the_body_raises() -> None:
        with pytest.raises(ValueError, match="body"):
            async with spawn("sleep", "60") as process:
                raise ValueError("body")
        await gone(process.pid)

    async def it_kills_a_program_whose_output_nobody_reads() -> None:
        async with asyncio.timeout(5):
            async with spawn("yes", stdout=asyncio.subprocess.PIPE) as process:
                await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM

    async def it_reads_lines_up_to_the_default_limit() -> None:
        line = b"x" * (2**16 - 1) + b"\n"
        async with spawn(
            "printf", "%s\\n", line[:-1].decode(), stdout=asyncio.subprocess.PIPE
        ) as process:
            assert await process.stdout.readline() == line

    async def it_refuses_a_line_past_the_default_limit() -> None:
        async with spawn(
            "head", "-c", str(2**16 + 1), "/dev/zero", stdout=asyncio.subprocess.PIPE
        ) as process:
            with pytest.raises(ValueError, match="limit"):
                await process.stdout.readline()

    async def it_reads_a_line_of_any_length_with_an_unbounded_limit() -> None:
        size = 2**24
        script = f"import sys; sys.stdout.write('x' * {size} + '\\nrest')"
        async with spawn(
            sys.executable, "-c", script, stdout=asyncio.subprocess.PIPE, limit=sys.maxsize
        ) as process:
            assert await process.stdout.readline() == b"x" * size + b"\n"
            assert await process.stdout.readline() == b"rest"
            assert await process.stdout.readline() == b""

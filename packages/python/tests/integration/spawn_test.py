import asyncio
import signal
import sys
from pathlib import Path

import pytest

from posix_tools import spawn
from posix_tools._spawn.group_alive import group_alive

IGNORE_TERM = (
    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "print('ready', flush=True); time.sleep(60)"
)


def describe_spawn() -> None:
    async def it_stops_the_whole_group_on_exit() -> None:
        async with spawn("sh", "-c", "sleep 60 & sleep 60", grace=2) as process:
            await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM
        assert not group_alive(process.pid)

    async def it_stops_the_group_when_the_body_raises() -> None:
        with pytest.raises(ValueError, match="body"):
            async with spawn("sleep", "60") as process:
                raise ValueError("body")
        assert not group_alive(process.pid)

    async def it_kills_a_group_that_ignores_signum_through_repeated_cancels() -> None:
        processes: list[asyncio.subprocess.Process] = []
        ready = asyncio.Event()

        async def run() -> None:
            async with spawn(
                sys.executable, "-c", IGNORE_TERM, stdout=asyncio.subprocess.PIPE, grace=0.5
            ) as process:
                processes.append(process)
                assert process.stdout is not None
                assert await process.stdout.readline() == b"ready\n"
                ready.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(run())
        async with asyncio.timeout(5):
            await ready.wait()
            task.cancel()
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        [process] = processes
        assert process.returncode == -signal.SIGKILL
        assert not group_alive(process.pid)

    async def it_lets_the_program_finish_within_linger(tmp_path: Path) -> None:
        path = tmp_path / "output"
        with path.open("wb") as output:
            async with spawn(
                "cat", stdin=asyncio.subprocess.PIPE, stdout=output, linger=5
            ) as process:
                assert process.stdin is not None
                process.stdin.write(b"saved\n")
            assert process.returncode == 0
            assert not output.closed
        assert path.read_bytes() == b"saved\n"

    async def it_drains_owned_pipes_nobody_reads() -> None:
        async with asyncio.timeout(5):
            async with spawn("yes", stdout=asyncio.subprocess.PIPE, grace=2) as process:
                await asyncio.sleep(0.1)
        assert process.returncode == -signal.SIGTERM
        assert process.stdout is not None
        assert process.stdout.at_eof()

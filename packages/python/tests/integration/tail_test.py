import asyncio
import signal
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from posix_tools import tail
from posix_tools._spawn.group_alive import group_alive

ROTATION = 15

OWNER = """
import asyncio, sys
from posix_tools import tail

start = asyncio.create_subprocess_exec

async def announce(*args, **options):
    process = await start(*args, **options)
    print(process.pid, flush=True)
    return process

asyncio.create_subprocess_exec = announce

async def main():
    async with tail(sys.argv[1], follow=True) as lines:
        await anext(lines)

asyncio.run(main())
"""


@pytest.fixture
def processes() -> Iterator[list[asyncio.subprocess.Process]]:
    started: list[asyncio.subprocess.Process] = []
    start = asyncio.create_subprocess_exec

    async def recording(*args: Any, **options: Any) -> asyncio.subprocess.Process:
        process = await start(*args, **options)
        started.append(process)
        return process

    with patch("asyncio.create_subprocess_exec", recording):
        yield started


async def gone(pgid: int) -> None:
    async with asyncio.timeout(5):
        while group_alive(pgid):
            await asyncio.sleep(0.05)


def numbered(count: int) -> bytes:
    return b"".join(b"%d\n" % i for i in range(count))


def describe_tail() -> None:
    def describe_awaited() -> None:
        async def it_returns_the_last_n_lines(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(numbered(20))
            assert await tail(path) == [b"%d\n" % i for i in range(10, 20)]
            assert await tail(path, n=1) == [b"19\n"]
            assert await tail(path, n=0) == []

        async def it_returns_the_whole_file_for_n_none(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(numbered(20))
            assert b"".join(await tail(path, n=None)) == numbered(20)

        async def it_reads_a_dash_prefixed_path(tmp_path: Path) -> None:
            path = tmp_path / "-n"
            path.write_bytes(b"dash\n")
            assert await tail(path) == [b"dash\n"]

        async def it_raises_for_a_missing_file(tmp_path: Path) -> None:
            with pytest.raises(FileNotFoundError):
                await tail(tmp_path / "missing")

        async def it_keeps_a_long_line_whole(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(b"x" * 200_000 + b"\nend\n")
            assert await tail(path, n=2) == [b"x" * 200_000 + b"\n", b"end\n"]

    def describe_followed() -> None:
        async def it_reads_existing_then_appended_lines(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(numbered(3))
            async with asyncio.timeout(5), tail(path, n=2, follow=True) as lines:
                assert [await anext(lines), await anext(lines)] == [b"1\n", b"2\n"]
                with path.open("ab") as file:
                    file.write(b"y" * 200_000 + b"\n")
                assert await anext(lines) == b"y" * 200_000 + b"\n"

        async def it_reads_a_dash_prefixed_path(tmp_path: Path) -> None:
            path = tmp_path / "-n"
            path.write_bytes(b"dash\n")
            async with asyncio.timeout(5), tail(path, follow=True) as lines:
                assert await anext(lines) == b"dash\n"

        async def it_waits_for_a_missing_file(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            async with asyncio.timeout(ROTATION), tail(path, follow=True) as lines:
                reading = asyncio.ensure_future(anext(lines))
                await asyncio.sleep(0.5)
                path.write_bytes(b"born\n")
                assert await reading == b"born\n"

        async def it_keeps_going_across_rotation(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(b"old\n")
            async with asyncio.timeout(ROTATION), tail(path, follow=True) as lines:
                assert await anext(lines) == b"old\n"
                path.rename(tmp_path / "app.log.1")
                path.write_bytes(b"new\n")
                assert await anext(lines) == b"new\n"

        async def it_keeps_a_half_read_line_across_a_cancelled_read(tmp_path: Path) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(b"")
            async with asyncio.timeout(5), tail(path, follow=True) as lines:
                with path.open("ab", buffering=0) as file:
                    file.write(b"half")
                    with pytest.raises(TimeoutError):
                        async with asyncio.timeout(0.5):
                            await anext(lines)
                    file.write(b" whole\n")
                assert await anext(lines) == b"half whole\n"

    def describe_stopping() -> None:
        async def it_reaps_tail_on_break(
            tmp_path: Path, processes: list[asyncio.subprocess.Process]
        ) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(numbered(3))
            async with asyncio.timeout(5), tail(path, follow=True) as lines:
                async for _ in lines:
                    break
            [process] = processes
            assert process.returncode is not None
            await gone(process.pid)

        async def it_reaps_tail_on_cancel(
            tmp_path: Path, processes: list[asyncio.subprocess.Process]
        ) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(b"")

            async def run() -> None:
                async with tail(path, follow=True) as lines:
                    await anext(lines)

            task = asyncio.create_task(run())
            async with asyncio.timeout(5):
                while not processes:
                    await asyncio.sleep(0.05)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            [process] = processes
            assert process.returncode is not None
            await gone(process.pid)

        async def it_reaps_tail_when_leaving_a_partial_read(
            tmp_path: Path, processes: list[asyncio.subprocess.Process]
        ) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(numbered(100_000))
            async with asyncio.timeout(5), tail(path, n=None) as lines:
                assert await anext(lines) == b"0\n"
            [process] = processes
            await gone(process.pid)

        @pytest.mark.parametrize("signum", [signal.SIGKILL, signal.SIGTERM])
        async def it_dies_with_its_owner(tmp_path: Path, signum: int) -> None:
            path = tmp_path / "app.log"
            path.write_bytes(b"")
            owner = await asyncio.create_subprocess_exec(
                sys.executable, "-c", OWNER, str(path), stdout=asyncio.subprocess.PIPE
            )
            assert owner.stdout is not None
            async with asyncio.timeout(5):
                pgid = int(await owner.stdout.readline())
            assert group_alive(pgid)
            owner.send_signal(signum)
            await owner.wait()
            await gone(pgid)

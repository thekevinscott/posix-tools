import asyncio
import os
import signal
import sys
from pathlib import Path

import pytest

from posix_tools import spawn

NOISY = """
import os, signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)
while True:
    os.write(1, b"x" * 65536)
"""


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

    async def it_kills_and_reaps_a_noisy_program_on_cancellation() -> None:
        started = asyncio.Event()
        running: list[asyncio.subprocess.Process] = []

        async def run() -> None:
            async with spawn(sys.executable, "-c", NOISY, stdout=asyncio.subprocess.PIPE) as proc:
                running.append(proc)
                started.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(run())
        await started.wait()
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert running[0].returncode == -signal.SIGKILL

    async def it_kills_and_reaps_a_noisy_program_on_body_failure() -> None:
        with pytest.raises(ValueError, match="body"):
            async with asyncio.timeout(5):
                async with spawn(
                    sys.executable, "-c", NOISY, stdout=asyncio.subprocess.PIPE
                ) as process:
                    await asyncio.sleep(0.1)
                    raise ValueError("body")
        assert process.returncode == -signal.SIGKILL

    async def it_sends_stdout_and_stderr_to_callable_sinks() -> None:
        out = bytearray()
        err = bytearray()
        script = 'import os; os.write(1, b"out"); os.write(2, b"err")'
        async with spawn(
            sys.executable, "-c", script, stdout=out.extend, stderr=err.extend
        ) as proc:
            await proc.wait()
        assert (bytes(out), bytes(err)) == (b"out", b"err")

    async def it_reads_sinks_in_64_kib_chunks() -> None:
        sizes: list[int] = []
        script = 'import os; os.write(1, b"x" * 65537)'
        async with spawn(
            sys.executable, "-c", script, stdout=lambda chunk: sizes.append(len(chunk))
        ) as proc:
            await proc.wait()
        assert sum(sizes) == 65537
        assert max(sizes) <= 65536

    async def it_passes_a_file_through_while_sinking_the_other_stream(tmp_path: Path) -> None:
        out = bytearray()
        script = 'import os; os.write(1, b"out"); os.write(2, b"err")'
        with (tmp_path / "stderr").open("wb") as file:
            async with spawn(sys.executable, "-c", script, stdout=out.extend, stderr=file) as proc:
                await proc.wait()
            assert not file.closed
        assert bytes(out) == b"out"
        assert (tmp_path / "stderr").read_bytes() == b"err"

    async def it_delivers_output_read_before_a_cancel() -> None:
        out = bytearray()
        seen = asyncio.Event()

        def sink(chunk: bytes) -> None:
            out.extend(chunk)
            seen.set()

        script = 'import os, time; os.write(1, b"partial"); time.sleep(60)'

        async def run() -> None:
            async with spawn(sys.executable, "-c", script, stdout=sink):
                await asyncio.Event().wait()

        task = asyncio.create_task(run())
        await seen.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert bytes(out) == b"partial"

    async def it_reaps_a_noisy_program_when_its_sink_fails() -> None:
        def full(_chunk: bytes) -> None:
            raise OSError("disk full")

        async def run() -> None:
            async with spawn(sys.executable, "-c", NOISY, stdout=full):
                await asyncio.Event().wait()

        with pytest.raises(OSError, match="disk full"):
            await asyncio.wait_for(run(), 5)

    async def it_drains_the_other_sink_after_one_sink_fails() -> None:
        err = bytearray()

        def full(_chunk: bytes) -> None:
            raise OSError("disk full")

        script = 'import os, time; os.write(1, b"out"); os.write(2, b"err"); time.sleep(60)'
        with pytest.raises(OSError, match="disk full"):
            async with asyncio.timeout(5):
                async with spawn(sys.executable, "-c", script, stdout=full, stderr=err.extend):
                    await asyncio.Event().wait()
        assert bytes(err) == b"err"

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

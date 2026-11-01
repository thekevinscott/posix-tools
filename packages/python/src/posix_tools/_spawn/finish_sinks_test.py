import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.finish_sinks import finish_sinks


def describe_finish_sinks() -> None:
    async def it_closes_stdin_drains_unsunk_output_and_waits() -> None:
        stdout = asyncio.StreamReader()
        stdin = Mock()
        process = Mock(stdin=stdin, stdout=stdout, stderr=None, wait=AsyncMock())
        with patch("posix_tools._spawn.finish_sinks.drain", new_callable=AsyncMock) as drain:
            await finish_sinks(process, {})
        stdin.close.assert_called_once_with()
        drain.assert_awaited_once_with(stdout, None)
        process.wait.assert_awaited_once_with()

    async def it_keeps_an_existing_drain_and_propagates_its_failure() -> None:
        stdout = asyncio.StreamReader()
        stderr = asyncio.StreamReader()
        gate = asyncio.Event()
        cancelled = asyncio.Event()

        async def waiting() -> int:
            try:
                await gate.wait()
                return 0
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def failed() -> None:
            raise OSError("sink full")

        existing = asyncio.create_task(failed())
        process = Mock(
            stdin=None, stdout=stdout, stderr=stderr, wait=AsyncMock(side_effect=waiting)
        )
        with (
            patch("posix_tools._spawn.finish_sinks.drain", new_callable=AsyncMock) as drain,
            pytest.raises(OSError, match="sink full"),
        ):
            drains = {stdout: existing, stderr: asyncio.create_task(drain(stderr, None))}
            await finish_sinks(process, drains)
        assert drain.await_count == 1
        await asyncio.sleep(0)
        assert cancelled.is_set()

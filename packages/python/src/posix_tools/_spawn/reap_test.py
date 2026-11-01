import asyncio
from unittest.mock import AsyncMock, Mock, patch

from posix_tools._spawn.reap import reap


def describe_reap() -> None:
    async def it_finishes_drains_then_discards_leftovers_and_waits() -> None:
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"leftover")
        stdout.feed_eof()
        process = Mock(stdout=stdout, stderr=None, wait=AsyncMock())

        async def failed() -> None:
            raise OSError("sink full")

        task = asyncio.create_task(failed())
        with patch("posix_tools._spawn.reap.drain", new_callable=AsyncMock) as drain:
            await reap(process, {stdout: task})
        drain.assert_awaited_once_with(stdout, None)
        process.wait.assert_awaited_once_with()

    async def it_disposes_both_streams() -> None:
        out = asyncio.StreamReader()
        err = asyncio.StreamReader()
        process = Mock(stdout=out, stderr=err, wait=AsyncMock())
        with patch("posix_tools._spawn.reap.drain", new_callable=AsyncMock) as drain:
            await reap(process, {})
        assert drain.await_count == 2

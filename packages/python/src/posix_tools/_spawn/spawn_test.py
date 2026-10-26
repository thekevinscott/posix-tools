import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.spawn import spawn


@pytest.fixture
def process() -> Mock:
    return Mock()


@pytest.fixture(autouse=True)
def start(process: Mock) -> Iterator[AsyncMock]:
    with patch(
        f"{__package__}.spawn.asyncio.create_subprocess_exec", autospec=True, return_value=process
    ) as m:
        yield m


@pytest.fixture(autouse=True)
def abandon() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.spawn.abandon", autospec=True) as m:
        yield m


@pytest.fixture(autouse=True)
def stop() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.spawn.stop", autospec=True) as m:
        yield m


def describe_spawn() -> None:
    async def it_starts_a_new_session_and_stops_it_on_exit(
        start: AsyncMock, stop: AsyncMock, process: Mock
    ) -> None:
        async with spawn("program", "arg", stdin=7, stdout=8, stderr=9) as proc:
            assert proc is process
            stop.assert_not_called()
        start.assert_awaited_once_with(
            "program", "arg", stdin=7, stdout=8, stderr=9, start_new_session=True
        )
        stop.assert_awaited_once_with(process)

    async def it_passes_no_streams_by_default(start: AsyncMock) -> None:
        async with spawn("program"):
            pass
        start.assert_awaited_once_with(
            "program", stdin=None, stdout=None, stderr=None, start_new_session=True
        )

    @pytest.mark.parametrize("error", [ValueError("body"), asyncio.CancelledError()])
    async def it_stops_when_the_body_fails(
        stop: AsyncMock, process: Mock, error: BaseException
    ) -> None:
        with pytest.raises(type(error)):
            async with spawn("program"):
                raise error
        stop.assert_awaited_once_with(process)

    async def it_finishes_stopping_through_a_cancel(stop: AsyncMock, process: Mock) -> None:
        stopping = asyncio.Event()
        stopped = asyncio.Event()

        async def slow_stop(_: Mock) -> None:
            stopping.set()
            await stopped.wait()

        stop.side_effect = slow_stop

        async def body() -> None:
            async with spawn("program"):
                pass

        task = asyncio.ensure_future(body())
        await stopping.wait()
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        stopped.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        stop.assert_awaited_once_with(process)

    async def it_raises_a_failed_start(start: AsyncMock, stop: AsyncMock) -> None:
        start.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            async with spawn("missing"):
                pass
        stop.assert_not_called()

    async def it_abandons_a_start_cancelled_midway(
        start: AsyncMock, abandon: AsyncMock, stop: AsyncMock, process: Mock
    ) -> None:
        launched = asyncio.Event()
        abandoned = asyncio.Event()

        async def slow_start(*_: object, **__: object) -> Mock:
            await launched.wait()
            return process

        async def slow_abandon(starting: asyncio.Future[Mock]) -> None:
            assert await starting is process
            abandoned.set()

        start.side_effect = slow_start
        abandon.side_effect = slow_abandon

        async def body() -> None:
            async with spawn("program"):
                pytest.fail("body ran")

        task = asyncio.ensure_future(body())
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        launched.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert abandoned.is_set()
        abandon.assert_awaited_once()
        stop.assert_not_called()

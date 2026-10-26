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
def stop() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.spawn.stop", autospec=True) as m:
        yield m


def stopped_with(stop: AsyncMock) -> object:
    assert stop.await_args is not None
    (starting,) = stop.await_args.args
    return starting.result()


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
        stop.assert_awaited_once()
        assert stopped_with(stop) is process

    async def it_passes_no_streams_by_default(start: AsyncMock) -> None:
        async with spawn("program"):
            pass
        start.assert_awaited_once_with(
            "program", stdin=None, stdout=None, stderr=None, start_new_session=True
        )

    @pytest.mark.parametrize("error", [ValueError("body"), asyncio.CancelledError()])
    async def it_stops_when_the_body_fails(stop: AsyncMock, error: BaseException) -> None:
        with pytest.raises(type(error)):
            async with spawn("program"):
                raise error
        stop.assert_awaited_once()

    async def it_raises_a_failed_start(start: AsyncMock, stop: AsyncMock) -> None:
        start.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            async with spawn("missing"):
                pytest.fail("body ran")
        stop.assert_awaited_once()

    async def it_raises_a_failed_stop(stop: AsyncMock) -> None:
        stop.side_effect = ValueError("stop")
        with pytest.raises(ValueError, match="stop"):
            async with spawn("program"):
                pass

    async def it_finishes_stopping_through_cancels(stop: AsyncMock) -> None:
        stopping = asyncio.Event()
        stopped = asyncio.Event()

        async def slow_stop(_: object) -> None:
            stopping.set()
            await stopped.wait()

        stop.side_effect = slow_stop

        async def body() -> None:
            async with spawn("program"):
                pass

        task = asyncio.ensure_future(body())
        await stopping.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        stopped.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        stop.assert_awaited_once()

    async def it_chains_a_failed_stop_to_the_cancel(stop: AsyncMock) -> None:
        stopping = asyncio.Event()

        async def failing_stop(_: object) -> None:
            stopping.set()
            await asyncio.sleep(0.01)
            raise ValueError("stop")

        stop.side_effect = failing_stop

        async def body() -> None:
            async with spawn("program"):
                pass

        task = asyncio.ensure_future(body())
        await stopping.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as raised:
            await task
        assert isinstance(raised.value.__cause__, ValueError)

    async def it_stops_a_start_cancelled_midway(
        start: AsyncMock, stop: AsyncMock, process: Mock
    ) -> None:
        launched = asyncio.Event()

        async def slow_start(*_: object, **__: object) -> Mock:
            await launched.wait()
            return process

        start.side_effect = slow_start

        async def awaits_start(starting: asyncio.Future[Mock]) -> None:
            await starting

        stop.side_effect = awaits_start

        async def body() -> None:
            async with spawn("program"):
                pytest.fail("body ran")

        task = asyncio.ensure_future(body())
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.01)
        launched.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        stop.assert_awaited_once()
        assert stopped_with(stop) is process

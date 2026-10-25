import asyncio
import signal
from collections.abc import Iterator
from typing import Any
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
def close() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.spawn.close", autospec=True) as m:
        yield m


def describe_spawn() -> None:
    @pytest.mark.parametrize("options", [{}, {"signum": signal.SIGINT, "grace": 0.5, "linger": 2}])
    async def it_starts_a_new_session_and_closes_with_its_options(
        start: AsyncMock, close: AsyncMock, process: Mock, options: dict[str, Any]
    ) -> None:
        drains = (asyncio.get_running_loop().create_future(),)
        async with spawn(
            "program", "arg", stdin=7, stdout=8, stderr=9, drains=drains, **options
        ) as proc:
            assert proc is process
            close.assert_not_called()
        start.assert_awaited_once_with(
            "program", "arg", stdin=7, stdout=8, stderr=9, start_new_session=True
        )
        expected = {"signum": signal.SIGTERM, "grace": 10, "linger": 0} | options
        close.assert_awaited_once_with(process, drains, **expected)

    @pytest.mark.parametrize("error", [ValueError("body"), asyncio.CancelledError()])
    async def it_skips_linger_when_the_body_fails(
        close: AsyncMock, process: Mock, error: BaseException
    ) -> None:
        with pytest.raises(type(error)):
            async with spawn("program", linger=2):
                raise error
        close.assert_awaited_once_with(process, (), signum=signal.SIGTERM, grace=10, linger=0)

    async def it_raises_a_failed_start(start: AsyncMock, close: AsyncMock) -> None:
        start.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            async with spawn("missing"):
                pass
        close.assert_not_called()

    def describe_cancelled_while_starting() -> None:
        @pytest.fixture
        def started(start: AsyncMock) -> asyncio.Event:
            event = asyncio.Event()
            process: Mock = start.return_value

            async def slow(*_: object, **__: object) -> Mock:
                await event.wait()
                if isinstance(start.return_value, BaseException):
                    raise start.return_value
                return process

            start.side_effect = slow
            return event

        async def run(started: asyncio.Event) -> None:
            async def body() -> None:
                async with spawn("program", signum=signal.SIGINT, grace=3, linger=2):
                    pytest.fail("body ran")

            task = asyncio.ensure_future(body())
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0.01)
            assert not task.done()
            started.set()
            with pytest.raises(asyncio.CancelledError):
                await task

        async def it_closes_what_it_started(
            started: asyncio.Event, close: AsyncMock, process: Mock
        ) -> None:
            await run(started)
            close.assert_awaited_once_with(process, (), signum=signal.SIGINT, grace=3, linger=0)

        async def it_has_nothing_to_close_when_the_start_fails(
            start: AsyncMock, started: asyncio.Event, close: AsyncMock
        ) -> None:
            start.return_value = OSError()
            await run(started)
            close.assert_not_called()

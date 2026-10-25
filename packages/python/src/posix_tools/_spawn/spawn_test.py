import asyncio
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.spawn import spawn

SIGINT = 2
SIGTERM = 15


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
def close() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.spawn.close", autospec=True) as m:
        yield m


def describe_spawn() -> None:
    @pytest.mark.parametrize("options", [{}, {"signum": SIGINT, "grace": 0.5, "linger": 2}])
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
        expected = {"signum": SIGTERM, "grace": 10, "linger": 0} | options
        close.assert_awaited_once_with(process, drains, **expected)

    @pytest.mark.parametrize("error", [ValueError("body"), asyncio.CancelledError()])
    async def it_skips_linger_when_the_body_fails(
        close: AsyncMock, process: Mock, error: BaseException
    ) -> None:
        with pytest.raises(type(error)):
            async with spawn("program", linger=2):
                raise error
        close.assert_awaited_once_with(process, (), signum=SIGTERM, grace=10, linger=0)

    async def it_raises_a_failed_start(start: AsyncMock, close: AsyncMock) -> None:
        start.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError):
            async with spawn("missing"):
                pass
        close.assert_not_called()

    async def it_abandons_a_start_cancelled_midway(
        start: AsyncMock, abandon: AsyncMock, close: AsyncMock, process: Mock
    ) -> None:
        launched = asyncio.Event()
        abandoned = asyncio.Event()

        async def slow_start(*_: object, **__: object) -> Mock:
            await launched.wait()
            return process

        async def slow_abandon(starting: asyncio.Future[Mock], **_: object) -> None:
            assert await starting is process
            abandoned.set()

        start.side_effect = slow_start
        abandon.side_effect = slow_abandon

        async def body() -> None:
            async with spawn("program", signum=SIGINT, grace=3, linger=2):
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
        assert abandon.await_args is not None
        assert abandon.await_args.kwargs == {"signum": SIGINT, "grace": 3}
        close.assert_not_called()

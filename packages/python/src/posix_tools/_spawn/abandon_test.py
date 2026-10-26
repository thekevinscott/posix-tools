import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.abandon import abandon


@pytest.fixture(autouse=True)
def stop() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.abandon.stop", autospec=True) as m:
        yield m


def describe_abandon() -> None:
    async def it_stops_what_the_start_launched(stop: AsyncMock) -> None:
        starting = asyncio.get_running_loop().create_future()
        process = Mock()
        starting.set_result(process)
        await abandon(starting)
        stop.assert_awaited_once_with(process)

    async def it_ignores_a_failed_start(stop: AsyncMock) -> None:
        starting = asyncio.get_running_loop().create_future()
        starting.set_exception(OSError())
        await abandon(starting)
        stop.assert_not_called()

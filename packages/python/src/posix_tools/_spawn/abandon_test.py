import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.abandon import abandon


@pytest.fixture(autouse=True)
def close() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.abandon.close", autospec=True) as m:
        yield m


def describe_abandon() -> None:
    async def it_closes_what_the_start_launched(close: AsyncMock) -> None:
        starting = asyncio.get_running_loop().create_future()
        process = Mock()
        starting.set_result(process)
        await abandon(starting, signum=2, grace=3)
        close.assert_awaited_once_with(process, (), signum=2, grace=3, linger=0)

    async def it_ignores_a_failed_start(close: AsyncMock) -> None:
        starting = asyncio.get_running_loop().create_future()
        starting.set_exception(OSError())
        await abandon(starting, signum=2, grace=3)
        close.assert_not_called()

    async def it_takes_options_by_keyword() -> None:
        with pytest.raises(TypeError):
            await abandon(Mock(), 2, 3)  # type: ignore[call-arg]

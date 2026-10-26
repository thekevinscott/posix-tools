from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from posix_tools._spawn.ended import ended


@pytest.fixture(autouse=True)
def group_alive() -> Iterator[Mock]:
    with patch(f"{__package__}.ended.group_alive", autospec=True, return_value=False) as m:
        yield m


def describe_ended() -> None:
    async def it_polls_until_the_leader_exits(group_alive: Mock) -> None:
        process = Mock(returncode=None, pid=7)

        async def exits(_: float) -> None:
            process.returncode = 0

        with patch(f"{__package__}.ended.asyncio.sleep", autospec=True, side_effect=exits) as sleep:
            await ended(process)
        sleep.assert_awaited_once_with(0.01)
        group_alive.assert_called_once_with(7)

    async def it_polls_until_the_group_is_gone(group_alive: Mock) -> None:
        group_alive.side_effect = [True, True, False]
        with patch(f"{__package__}.ended.asyncio.sleep", autospec=True) as sleep:
            await ended(Mock(returncode=0, pid=7))
        assert sleep.await_count == 2
        group_alive.assert_called_with(7)

    async def it_returns_at_once_for_an_exited_leader_and_gone_group() -> None:
        with patch(f"{__package__}.ended.asyncio.sleep", autospec=True) as sleep:
            await ended(Mock(returncode=0, pid=7))
        sleep.assert_not_called()

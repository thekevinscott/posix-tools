import asyncio
from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from posix_tools._spawn.ended import ended


@pytest.fixture(autouse=True)
def group_alive() -> Iterator[Mock]:
    with patch(f"{__package__}.ended.group_alive", autospec=True, return_value=False) as m:
        yield m


def describe_ended() -> None:
    async def it_waits_for_exit_then_drains_then_the_group(group_alive: Mock) -> None:
        process = Mock(returncode=None, pid=7)
        drain = asyncio.get_running_loop().create_future()
        group_alive.side_effect = [True, False]
        waiting = asyncio.ensure_future(ended(process, [drain]))
        await asyncio.sleep(0.03)
        assert not waiting.done()
        process.returncode = 0
        await asyncio.sleep(0.03)
        assert not waiting.done()
        group_alive.assert_not_called()
        drain.set_exception(OSError())
        await asyncio.wait_for(waiting, 1)
        assert group_alive.call_count == 2
        group_alive.assert_called_with(7)

    async def it_leaves_drains_running_when_cancelled() -> None:
        drain = asyncio.get_running_loop().create_future()
        waiting = asyncio.ensure_future(ended(Mock(returncode=0), [drain]))
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert not drain.cancelled()

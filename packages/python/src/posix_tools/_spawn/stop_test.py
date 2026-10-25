import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from posix_tools._spawn.stop import stop

SIGINT = 2
SIGKILL = 9
SIGTERM = 15


@pytest.fixture(autouse=True)
def killpg() -> Iterator[Mock]:
    with patch(f"{__package__}.stop.os.killpg", autospec=True) as m:
        yield m


@pytest.fixture(autouse=True)
def group_alive() -> Iterator[Mock]:
    with patch(f"{__package__}.stop.group_alive", autospec=True, return_value=True) as m:
        yield m


@pytest.fixture(autouse=True)
def ended() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.stop.ended", autospec=True) as m:
        yield m


async def forever(*_: object) -> None:
    await asyncio.Event().wait()


def describe_stop() -> None:
    async def it_signals_the_group_and_waits(killpg: Mock, ended: AsyncMock) -> None:
        process = Mock(returncode=None, pid=7)
        drains = [Mock()]
        await stop(process, drains, signum=SIGINT, grace=1)
        killpg.assert_called_once_with(7, SIGINT)
        ended.assert_awaited_once_with(process, drains)

    async def it_escalates_to_sigkill_after_grace(killpg: Mock, ended: AsyncMock) -> None:
        hangs = [True, False]

        async def first_hangs(*_: object) -> None:
            if hangs.pop(0):
                await forever()

        ended.side_effect = first_hangs
        await stop(Mock(returncode=None, pid=7), [], signum=SIGTERM, grace=0.01)
        assert killpg.call_args_list == [call(7, SIGTERM), call(7, SIGKILL)]

    async def it_warns_when_the_group_outlives_sigkill(ended: AsyncMock) -> None:
        ended.side_effect = forever
        with pytest.warns(RuntimeWarning, match="process group 7 did not stop") as warned:
            await stop(Mock(returncode=None, pid=7), [], signum=SIGTERM, grace=0.01)
        assert warned[0].filename == __file__

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_ignores_signal_errors(killpg: Mock, error: type[OSError]) -> None:
        killpg.side_effect = error
        await stop(Mock(returncode=None, pid=7), [], signum=SIGTERM, grace=1)

    async def it_takes_options_by_keyword() -> None:
        with pytest.raises(TypeError):
            await stop(Mock(), [], SIGTERM, 1)  # type: ignore[call-arg]

    async def it_does_not_signal_a_group_that_is_gone(
        killpg: Mock, ended: AsyncMock, group_alive: Mock
    ) -> None:
        group_alive.return_value = False
        process = Mock(returncode=0, pid=7)
        await stop(process, [], signum=SIGTERM, grace=1)
        killpg.assert_not_called()
        ended.assert_awaited_once_with(process, [])

    async def it_bounds_the_wait_once_the_group_is_gone(
        killpg: Mock, ended: AsyncMock, group_alive: Mock
    ) -> None:
        group_alive.return_value = False
        ended.side_effect = forever
        await stop(Mock(returncode=0, pid=7), [], signum=SIGTERM, grace=0.01)
        killpg.assert_not_called()

    async def it_signals_an_exited_leader_whose_group_lives_on(killpg: Mock) -> None:
        await stop(Mock(returncode=0, pid=7), [], signum=SIGTERM, grace=1)
        killpg.assert_called_once_with(7, SIGTERM)

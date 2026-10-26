import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from posix_tools._spawn.stop import GRACE, stop

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


@pytest.fixture
def short_grace() -> Iterator[None]:
    with patch(f"{__package__}.stop.GRACE", 0.01):
        yield


async def forever(*_: object) -> None:
    await asyncio.Event().wait()


def describe_stop() -> None:
    def it_gives_ten_seconds_of_grace() -> None:
        assert GRACE == 10

    async def it_terminates_the_group_and_waits(killpg: Mock, ended: AsyncMock) -> None:
        process = Mock(returncode=None, pid=7)
        await stop(process)
        killpg.assert_called_once_with(7, SIGTERM)
        ended.assert_awaited_once_with(process)

    @pytest.mark.usefixtures("short_grace")
    async def it_escalates_to_sigkill_after_grace(killpg: Mock, ended: AsyncMock) -> None:
        hangs = [True, False]

        async def first_hangs(*_: object) -> None:
            if hangs.pop(0):
                await forever()

        ended.side_effect = first_hangs
        await stop(Mock(returncode=None, pid=7))
        assert killpg.call_args_list == [call(7, SIGTERM), call(7, SIGKILL)]

    @pytest.mark.usefixtures("short_grace")
    async def it_warns_when_the_group_outlives_sigkill(ended: AsyncMock) -> None:
        ended.side_effect = forever
        with pytest.warns(RuntimeWarning, match="process group 7 did not stop") as warned:
            await stop(Mock(returncode=None, pid=7))
        assert warned[0].filename == __file__

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_ignores_signal_errors(killpg: Mock, error: type[OSError]) -> None:
        killpg.side_effect = error
        await stop(Mock(returncode=None, pid=7))

    async def it_does_not_signal_a_group_that_is_gone(
        killpg: Mock, ended: AsyncMock, group_alive: Mock
    ) -> None:
        group_alive.return_value = False
        await stop(Mock(returncode=0, pid=7))
        group_alive.assert_called_once_with(7)
        killpg.assert_not_called()
        ended.assert_not_called()

    async def it_signals_an_exited_leader_whose_group_lives_on(killpg: Mock) -> None:
        await stop(Mock(returncode=0, pid=7))
        killpg.assert_called_once_with(7, SIGTERM)

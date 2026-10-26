import asyncio
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock, call, patch

import pytest

from posix_tools._spawn.stop import GRACE, POLL, stop

SIGKILL = 9
SIGTERM = 15


@pytest.fixture(autouse=True)
def killpg() -> Iterator[Mock]:
    with patch(f"{__package__}.stop.os.killpg", autospec=True) as m:
        yield m


@pytest.fixture(autouse=True)
def group_alive() -> Iterator[Mock]:
    with patch(f"{__package__}.stop.group_alive", autospec=True, return_value=False) as m:
        yield m


@pytest.fixture
def short_grace() -> Iterator[None]:
    with patch(f"{__package__}.stop.GRACE", 0.01):
        yield


def started(process: Mock) -> asyncio.Future[Any]:
    future = asyncio.get_running_loop().create_future()
    future.set_result(process)
    return future


def exits_on(sent: int, process: Mock) -> object:
    def killpg(_: int, signum: int) -> None:
        if signum == sent:
            process.returncode = -signum

    return killpg


def describe_stop() -> None:
    def it_gives_ten_seconds_of_grace_polling_every_10ms() -> None:
        assert GRACE == 10
        assert POLL == 0.01

    async def it_does_nothing_for_a_failed_start(killpg: Mock) -> None:
        future = asyncio.get_running_loop().create_future()
        future.set_exception(OSError())
        await stop(future)
        killpg.assert_not_called()

    async def it_terminates_the_group_and_waits_for_the_leader(killpg: Mock) -> None:
        process = Mock(returncode=None, pid=7)
        killpg.side_effect = exits_on(SIGTERM, process)
        await stop(started(process))
        killpg.assert_called_once_with(7, SIGTERM)

    async def it_waits_for_the_rest_of_the_group(killpg: Mock, group_alive: Mock) -> None:
        process = Mock(returncode=None, pid=7)
        killpg.side_effect = exits_on(SIGTERM, process)
        group_alive.side_effect = [True, True, False]
        with patch(f"{__package__}.stop.asyncio.sleep", autospec=True) as sleep:
            await stop(started(process))
        assert sleep.await_count == 2
        sleep.assert_awaited_with(POLL)
        group_alive.assert_called_with(7)

    @pytest.mark.usefixtures("short_grace")
    async def it_escalates_to_sigkill_after_grace(killpg: Mock) -> None:
        process = Mock(returncode=None, pid=7)
        killpg.side_effect = exits_on(SIGKILL, process)
        await stop(started(process))
        assert killpg.call_args_list == [call(7, SIGTERM), call(7, SIGKILL)]

    @pytest.mark.usefixtures("short_grace")
    async def it_warns_when_the_group_outlives_sigkill() -> None:
        with pytest.warns(RuntimeWarning, match="process group 7 did not stop") as warned:
            await stop(started(Mock(returncode=None, pid=7)))
        assert warned[0].filename == __file__

    @pytest.mark.usefixtures("short_grace")
    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_ignores_signal_errors(killpg: Mock, error: type[OSError]) -> None:
        killpg.side_effect = error
        with pytest.warns(RuntimeWarning):
            await stop(started(Mock(returncode=None, pid=7)))
        assert killpg.call_count == 2

    async def it_does_not_signal_a_group_that_is_gone(killpg: Mock, group_alive: Mock) -> None:
        await stop(started(Mock(returncode=0, pid=7)))
        group_alive.assert_called_once_with(7)
        killpg.assert_not_called()

    async def it_signals_an_exited_leader_whose_group_lives_on(
        killpg: Mock, group_alive: Mock
    ) -> None:
        group_alive.side_effect = [True, False]
        await stop(started(Mock(returncode=0, pid=7)))
        killpg.assert_called_once_with(7, SIGTERM)

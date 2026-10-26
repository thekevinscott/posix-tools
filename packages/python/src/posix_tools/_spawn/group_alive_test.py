from collections.abc import Iterator
from unittest.mock import Mock, patch

import psutil
import pytest

from posix_tools._spawn.group_alive import group_alive


def proc(pid: int, status: str | None = psutil.STATUS_RUNNING) -> Mock:
    return Mock(pid=pid, info={"status": status})


@pytest.fixture
def process_iter() -> Iterator[Mock]:
    with patch(f"{__package__}.group_alive.psutil.process_iter", autospec=True) as m:
        yield m


@pytest.fixture
def getpgid() -> Iterator[Mock]:
    groups = {10: 6, 11: 7, 12: 8}
    with patch(f"{__package__}.group_alive.os.getpgid", autospec=True) as m:
        m.side_effect = groups.__getitem__
        yield m


def describe_group_alive() -> None:
    def it_asks_only_for_status(process_iter: Mock) -> None:
        process_iter.return_value = []
        assert not group_alive(7)
        process_iter.assert_called_once_with(["status"])

    @pytest.mark.parametrize(
        "status", [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING, psutil.STATUS_DISK_SLEEP, None]
    )
    def it_is_true_when_a_live_member_exists(
        process_iter: Mock, getpgid: Mock, status: str | None
    ) -> None:
        process_iter.return_value = [proc(10), proc(11, status), proc(12)]
        assert group_alive(7)
        getpgid.assert_called_with(11)

    def it_is_false_when_no_process_is_in_the_group(process_iter: Mock, getpgid: Mock) -> None:
        process_iter.return_value = [proc(10), proc(12)]
        assert not group_alive(7)
        assert getpgid.call_count == 2

    @pytest.mark.parametrize("status", [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD])
    def it_skips_dead_members(process_iter: Mock, getpgid: Mock, status: str) -> None:
        process_iter.return_value = [proc(11, status)]
        assert not group_alive(7)
        getpgid.assert_not_called()

    def it_skips_pid_zero(process_iter: Mock, getpgid: Mock) -> None:
        process_iter.return_value = [proc(0)]
        assert not group_alive(7)
        getpgid.assert_not_called()

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    def it_skips_a_process_it_cannot_look_up(
        process_iter: Mock, getpgid: Mock, error: type[Exception]
    ) -> None:
        process_iter.return_value = [proc(10), proc(11)]
        getpgid.side_effect = [error, 7]
        assert group_alive(7)

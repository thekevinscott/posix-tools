from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from posix_tools._spawn.group_alive import group_alive

PGID = 7000


def proc(pid: int, status: str | None = "running") -> Mock:
    return Mock(pid=pid, info={"status": status})


@pytest.fixture
def process_iter() -> Iterator[Mock]:
    with patch(f"{__package__}.group_alive.psutil.process_iter", autospec=True) as m:
        yield m


@pytest.fixture
def getpgid() -> Iterator[Mock]:
    groups = {10: PGID - 1, 11: PGID, 12: PGID + 1}
    with patch(f"{__package__}.group_alive.os.getpgid", autospec=True) as m:
        # A fresh int, so an identity check fails where equality holds.
        m.side_effect = lambda pid: int(str(groups[pid]))
        yield m


def describe_group_alive() -> None:
    def it_asks_only_for_status(process_iter: Mock) -> None:
        process_iter.return_value = []
        assert not group_alive(PGID)
        process_iter.assert_called_once_with(["status"])

    @pytest.mark.parametrize("status", ["running", "sleeping", "disk-sleep", None])
    def it_is_true_when_a_live_member_exists(
        process_iter: Mock, getpgid: Mock, status: str | None
    ) -> None:
        process_iter.return_value = [proc(10), proc(11, status), proc(12)]
        assert group_alive(PGID)
        getpgid.assert_called_with(11)

    def it_is_false_when_no_process_is_in_the_group(process_iter: Mock, getpgid: Mock) -> None:
        process_iter.return_value = [proc(10), proc(12)]
        assert not group_alive(PGID)
        assert getpgid.call_count == 2

    @pytest.mark.parametrize("status", ["zombie", "dead"])
    def it_skips_dead_members(process_iter: Mock, getpgid: Mock, status: str) -> None:
        process_iter.return_value = [proc(11, status)]
        assert not group_alive(PGID)
        getpgid.assert_not_called()

    def it_keeps_looking_past_a_dead_member(process_iter: Mock, getpgid: Mock) -> None:
        process_iter.return_value = [proc(10, "zombie"), proc(11)]
        assert group_alive(PGID)
        getpgid.assert_called_once_with(11)

    def it_skips_pid_zero(process_iter: Mock, getpgid: Mock) -> None:
        process_iter.return_value = [proc(0)]
        assert not group_alive(PGID)
        getpgid.assert_not_called()

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    def it_skips_a_process_it_cannot_look_up(
        process_iter: Mock, getpgid: Mock, error: type[Exception]
    ) -> None:
        process_iter.return_value = [proc(10), proc(11)]
        getpgid.side_effect = [error, PGID]
        assert group_alive(PGID)

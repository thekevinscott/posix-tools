import subprocess
from collections.abc import Iterator
from unittest.mock import Mock, call, patch

import pytest

from posix_tools._spawn.watch import WATCHER, watch

LIFETIME = 3
OWNER = 4


@pytest.fixture
def calls() -> Mock:
    return Mock()


@pytest.fixture(autouse=True)
def pipe() -> Iterator[Mock]:
    with patch(f"{__package__}.watch.os.pipe", autospec=True, return_value=(LIFETIME, OWNER)) as m:
        yield m


@pytest.fixture(autouse=True)
def close(calls: Mock) -> Iterator[Mock]:
    with patch(f"{__package__}.watch.os.close", autospec=True) as m:
        calls.attach_mock(m, "close")
        yield m


@pytest.fixture(autouse=True)
def popen(calls: Mock) -> Iterator[Mock]:
    with patch(f"{__package__}.watch.subprocess.Popen", autospec=True) as m:
        calls.attach_mock(m, "popen")
        yield m


def describe_watch() -> None:
    def it_starts_a_watcher_that_kills_the_group_on_eof(popen: Mock) -> None:
        with watch(7):
            popen.assert_called_once_with(
                ("sh", "-c", WATCHER, "sh", "7"),
                stdin=LIFETIME,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        assert WATCHER == 'read -r _; kill -KILL -"$1"'

    def it_hands_over_the_read_end_and_holds_the_write_end(calls: Mock) -> None:
        with watch(7):
            assert calls.mock_calls[-1] == call.close(LIFETIME)
            assert call.close(OWNER) not in calls.mock_calls

    def it_stops_the_watcher_before_letting_go(calls: Mock) -> None:
        with watch(7):
            pass
        watcher = call.popen()
        assert calls.mock_calls[-3:] == [watcher.kill(), watcher.wait(), call.close(OWNER)]

    def it_stops_the_watcher_when_the_body_raises(calls: Mock) -> None:
        with pytest.raises(ValueError, match="body"), watch(7):
            raise ValueError("body")
        watcher = call.popen()
        assert calls.mock_calls[-3:] == [watcher.kill(), watcher.wait(), call.close(OWNER)]

    def it_closes_both_ends_when_the_watcher_fails_to_start(popen: Mock, close: Mock) -> None:
        popen.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError), watch(7):
            pytest.fail("body ran")
        assert close.call_args_list == [call(LIFETIME), call(OWNER)]

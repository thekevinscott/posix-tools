from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from posix_tools._spawn.group_alive import group_alive


@pytest.fixture(autouse=True)
def running_in() -> Iterator[Mock]:
    with patch(f"{__package__}.group_alive.running_in", autospec=True, return_value=False) as m:
        yield m


def describe_group_alive() -> None:
    def describe_with_proc() -> None:
        @pytest.fixture
        def proc(tmp_path: Path) -> Iterator[Path]:
            for name in ("10", "11", "self"):
                (tmp_path / name).mkdir()
                (tmp_path / name / "stat").touch()
            with patch(f"{__package__}.group_alive.PROC", tmp_path):
                yield tmp_path

        def it_checks_each_numeric_process(proc: Path, running_in: Mock) -> None:
            assert not group_alive(7)
            assert sorted(running_in.call_args_list) == [
                call(proc / "10" / "stat", 7),
                call(proc / "11" / "stat", 7),
            ]

        @pytest.mark.usefixtures("proc")
        def it_is_true_when_any_member_runs(running_in: Mock) -> None:
            running_in.side_effect = lambda stat, _: stat.parent.name == "11"
            assert group_alive(7)

    def describe_without_proc() -> None:
        @pytest.fixture
        def killpg(tmp_path: Path) -> Iterator[Mock]:
            with (
                patch(f"{__package__}.group_alive.PROC", tmp_path / "missing"),
                patch(f"{__package__}.group_alive.os.killpg", autospec=True) as m,
            ):
                yield m

        def it_probes_the_group(killpg: Mock) -> None:
            assert group_alive(7)
            killpg.assert_called_once_with(7, 0)

        def it_is_false_when_the_group_is_gone(killpg: Mock) -> None:
            killpg.side_effect = ProcessLookupError
            assert not group_alive(7)

        def it_counts_a_group_it_may_not_signal(killpg: Mock) -> None:
            killpg.side_effect = PermissionError
            assert group_alive(7)

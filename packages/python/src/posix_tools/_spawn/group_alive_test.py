import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from posix_tools._spawn.group_alive import group_alive


def stat(proc: Path, pid: int, state: str, pgid: int) -> None:
    (proc / str(pid)).mkdir()
    (proc / str(pid) / "stat").write_text(f"{pid} (a) b) {state} 1 {pgid} {pgid} 0\n")


def describe_group_alive() -> None:
    def describe_with_proc() -> None:
        @pytest.fixture
        def proc(tmp_path: Path) -> Iterator[Path]:
            with patch(f"{__package__}.group_alive.PROC", tmp_path):
                yield tmp_path

        def it_finds_a_running_member(proc: Path) -> None:
            stat(proc, 10, "Z", 7)
            stat(proc, 11, "S", 7)
            assert group_alive(7)

        def it_skips_zombies_and_other_groups(proc: Path) -> None:
            stat(proc, 10, "Z", 7)
            stat(proc, 11, "X", 7)
            stat(proc, 12, "R", 8)
            assert not group_alive(7)

        def it_skips_processes_that_vanish(proc: Path) -> None:
            (proc / "10" / "stat").mkdir(parents=True)
            assert not group_alive(7)

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

    def it_sees_its_own_group() -> None:
        assert group_alive(os.getpgrp())

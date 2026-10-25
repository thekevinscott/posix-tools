from pathlib import Path

import pytest

from posix_tools._spawn.running_in import running_in


def stat(tmp_path: Path, state: str, pgid: int) -> Path:
    path = tmp_path / "stat"
    path.write_text(f"10 (a) b) {state} 1 {pgid} 99 0\n")
    return path


def describe_running_in() -> None:
    @pytest.mark.parametrize("state", ["R", "S", "D"])
    def it_counts_a_live_member(tmp_path: Path, state: str) -> None:
        assert running_in(stat(tmp_path, state, 7), 7)

    @pytest.mark.parametrize("state", ["Z", "X"])
    def it_skips_dead_members(tmp_path: Path, state: str) -> None:
        assert not running_in(stat(tmp_path, state, 7), 7)

    @pytest.mark.parametrize("pgid", [6, 8, 99])
    def it_skips_other_groups(tmp_path: Path, pgid: int) -> None:
        assert not running_in(stat(tmp_path, "R", pgid), 7)

    def it_skips_a_process_that_vanished(tmp_path: Path) -> None:
        assert not running_in(tmp_path / "missing", 7)

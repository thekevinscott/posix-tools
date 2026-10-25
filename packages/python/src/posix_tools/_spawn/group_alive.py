import os
from pathlib import Path

PROC = Path("/proc")


def group_alive(pgid: int) -> bool:
    # killpg counts zombies, which an init that never reaps can leave forever. /proc can skip them.
    if PROC.is_dir():
        return any(running_in(stat, pgid) for stat in PROC.glob("[0-9]*/stat"))
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def running_in(stat: Path, pgid: int) -> bool:
    try:
        fields = stat.read_text().rsplit(")", 1)[1].split()
    except OSError:
        return False
    return fields[2] == str(pgid) and fields[0] not in ("Z", "X")

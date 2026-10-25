import os
from pathlib import Path

from posix_tools._spawn.running_in import running_in

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

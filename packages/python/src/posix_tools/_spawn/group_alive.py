import os

import psutil

GONE = {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}


def group_alive(pgid: int) -> bool:
    # killpg counts zombies, which an init that never reaps can leave forever.
    for process in psutil.process_iter(["status"]):
        # macOS lists the kernel as pid 0, and getpgid(0) means the caller.
        if not process.pid or process.info["status"] in GONE:
            continue
        try:
            if os.getpgid(process.pid) == pgid:
                return True
        except (ProcessLookupError, PermissionError):
            continue
    return False

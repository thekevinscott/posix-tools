import asyncio
import os
import signal
import warnings
from contextlib import suppress

from posix_tools._spawn.ended import ended
from posix_tools._spawn.group_alive import group_alive

GRACE = 10


async def stop(process: asyncio.subprocess.Process) -> None:
    # Once the leader is reaped its pid, and so the group id, can be reused.
    if process.returncode is not None and not group_alive(process.pid):
        return
    for sent in (signal.SIGTERM, signal.SIGKILL):
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, sent)
        try:
            async with asyncio.timeout(GRACE):
                await ended(process)
        except TimeoutError:
            continue
        return
    warnings.warn(f"process group {process.pid} did not stop", RuntimeWarning, stacklevel=2)

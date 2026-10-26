import asyncio
import os
import signal
import warnings
from contextlib import suppress

from posix_tools._spawn.group_alive import group_alive

GRACE = 10
POLL = 0.01


async def stop(starting: asyncio.Future[asyncio.subprocess.Process]) -> None:
    try:
        process = await starting
    except Exception:
        return
    # Once the leader is reaped its pid, and so the group id, can be reused.
    if process.returncode is not None and not group_alive(process.pid):
        return
    for sent in (signal.SIGTERM, signal.SIGKILL):
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, sent)
        try:
            async with asyncio.timeout(GRACE):
                # process.wait() also waits for every holder of the pipes to close them.
                while process.returncode is None or group_alive(process.pid):
                    await asyncio.sleep(POLL)
        except TimeoutError:
            continue
        return
    warnings.warn(f"process group {process.pid} did not stop", RuntimeWarning, stacklevel=2)

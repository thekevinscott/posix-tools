import asyncio
import os
import signal
import warnings
from collections.abc import Sequence
from contextlib import suppress
from typing import Any

from posix_tools._spawn.ended import ended
from posix_tools._spawn.group_alive import group_alive
from posix_tools._spawn.within import within


async def stop(
    process: asyncio.subprocess.Process,
    waiting: Sequence[asyncio.Future[Any]],
    *,
    signum: int,
    grace: float,
) -> None:
    # Once the leader is reaped its pid, and so the group id, can be reused.
    if process.returncode is not None and not group_alive(process.pid):
        await within(grace, ended(process, waiting))
        return
    for sent in (signum, signal.SIGKILL):
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, sent)
        if await within(grace, ended(process, waiting)):
            return
    warnings.warn(f"process group {process.pid} did not stop", RuntimeWarning, stacklevel=2)

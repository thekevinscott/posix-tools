import asyncio
import os
import signal
from contextlib import suppress


def terminate(starting: asyncio.Future[asyncio.subprocess.Process]) -> None:
    if not starting.cancelled() and starting.exception() is None:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(starting.result().pid, signal.SIGTERM)

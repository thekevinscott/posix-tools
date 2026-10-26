import asyncio

from posix_tools._spawn.group_alive import group_alive

POLL = 0.01


async def ended(process: asyncio.subprocess.Process) -> None:
    # process.wait() also waits for every holder of the pipes to close them.
    while process.returncode is None or group_alive(process.pid):
        await asyncio.sleep(POLL)

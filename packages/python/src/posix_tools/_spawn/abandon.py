import asyncio

from posix_tools._spawn.stop import stop


async def abandon(starting: asyncio.Future[asyncio.subprocess.Process]) -> None:
    try:
        process = await starting
    except Exception:
        return
    await stop(process)

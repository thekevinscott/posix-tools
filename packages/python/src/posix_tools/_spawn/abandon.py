import asyncio

from posix_tools._spawn.close import close


async def abandon(
    starting: asyncio.Future[asyncio.subprocess.Process], *, signum: int, grace: float
) -> None:
    try:
        process = await starting
    except Exception:
        return
    await close(process, (), signum=signum, grace=grace, linger=0)

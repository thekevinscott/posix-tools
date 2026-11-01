import asyncio

from posix_tools._spawn.drain import drain


async def reap(
    process: asyncio.subprocess.Process,
    drains: dict[asyncio.StreamReader, asyncio.Task[None]],
) -> None:
    await asyncio.gather(*drains.values(), return_exceptions=True)
    for reader in (process.stdout, process.stderr):
        if reader is not None:
            await drain(reader, None)
    await process.wait()

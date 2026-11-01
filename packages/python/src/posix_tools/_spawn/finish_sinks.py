import asyncio

from posix_tools._spawn.drain import drain


async def finish_sinks(
    process: asyncio.subprocess.Process,
    drains: dict[asyncio.StreamReader, asyncio.Task[None]],
) -> None:
    if process.stdin is not None:
        process.stdin.close()
    for reader in (process.stdout, process.stderr):
        if reader is not None and reader not in drains:
            drains[reader] = asyncio.create_task(drain(reader, None))
    exited = asyncio.create_task(process.wait())
    try:
        done, _ = await asyncio.wait(
            {exited, *drains.values()}, return_when=asyncio.FIRST_EXCEPTION
        )
        for task in done:
            task.result()
    finally:
        if not exited.done():
            exited.cancel()

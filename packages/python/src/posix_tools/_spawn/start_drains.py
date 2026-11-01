import asyncio

from posix_tools._spawn.drain import drain
from posix_tools._spawn.types import Sink


def start_drains(
    process: asyncio.subprocess.Process,
    sinks: tuple[Sink | None, Sink | None],
    errors: list[BaseException],
    owner: asyncio.Task[object] | None,
) -> dict[asyncio.StreamReader, asyncio.Task[None]]:
    drains: dict[asyncio.StreamReader, asyncio.Task[None]] = {}

    def failed(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (error := task.exception()) is not None:
            errors.append(error)
            if owner is not None:
                owner.cancel()

    for reader, sink in zip((process.stdout, process.stderr), sinks, strict=True):
        if reader is not None and sink is not None:
            task = asyncio.create_task(drain(reader, sink))
            task.add_done_callback(failed)
            drains[reader] = task
    return drains

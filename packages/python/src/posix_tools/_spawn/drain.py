import asyncio

from posix_tools._spawn.types import Sink

CHUNK_BYTES = 65536


async def drain(reader: asyncio.StreamReader, sink: Sink | None) -> None:
    while chunk := await reader.read(CHUNK_BYTES):
        if sink is not None:
            sink(chunk)

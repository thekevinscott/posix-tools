import asyncio
from typing import Self


class Lines:
    """Iterate a stream's lines, keeping a half-read line across a cancelled read.

    A class, not an async generator: cancelling a generator's `__anext__` closes it for good.
    """

    def __init__(self, stream: asyncio.StreamReader) -> None:
        self._stream = stream
        self._chunks: list[bytes] = []

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        while True:
            try:
                chunk = await self._stream.readuntil(b"\n")
            except asyncio.LimitOverrunError as error:
                self._chunks.append(await self._stream.readexactly(error.consumed))
                continue
            except asyncio.IncompleteReadError as error:
                chunk = error.partial
                if not chunk and not self._chunks:
                    raise StopAsyncIteration from None
            line = b"".join([*self._chunks, chunk])
            self._chunks.clear()
            return line

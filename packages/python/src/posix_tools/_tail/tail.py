import os
from collections.abc import AsyncIterator, Generator
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType
from typing import Any

from posix_tools._tail.follow import follow
from posix_tools._tail.lines import Lines
from posix_tools._tail.read import read


class tail:
    """Read the end of a file, or follow it as it grows.

    Use with `async with` to stream lines, or `await` for all of them.
    """

    def __init__(
        self, path: str | os.PathLike[str], n: int | None = 10, follow: bool = False
    ) -> None:
        if n is not None and n < 0:
            raise ValueError(f"n must be None or >= 0, got {n}")
        self._path = Path(path)
        self._count = "+1" if n is None else str(n)
        self._follow = follow
        self._context: AbstractAsyncContextManager[Lines] | None = None

    async def __aenter__(self) -> AsyncIterator[bytes]:
        opener = follow if self._follow else read
        self._context = opener(self._path, self._count)
        return await self._context.__aenter__()

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        assert self._context is not None
        return await self._context.__aexit__(kind, error, traceback)

    def __await__(self) -> Generator[Any, None, list[bytes]]:
        if self._follow:
            raise TypeError("cannot await tail(follow=True), its stream never ends; use async with")
        return self._collect().__await__()

    async def _collect(self) -> list[bytes]:
        async with self as lines:
            return [line async for line in lines]

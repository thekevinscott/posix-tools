import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from posix_tools._tail.read import read

type Calls = list[tuple[tuple[str, ...], dict[str, Any]]]


@pytest.fixture
def calls() -> Iterator[Calls]:
    recorded: Calls = []

    @asynccontextmanager
    async def spawn(*args: str, **options: Any) -> AsyncIterator[Mock]:
        recorded.append((args, options))
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"a\nb\n")
        stdout.feed_eof()
        yield Mock(stdout=stdout)

    with patch(f"{__package__}.read.spawn", spawn):
        yield recorded


def describe_read() -> None:
    async def it_runs_tail_on_the_open_file_and_yields_its_lines(
        tmp_path: Path, calls: Calls
    ) -> None:
        path = tmp_path / "log"
        path.write_bytes(b"")
        async with read(path, "5") as lines:
            assert [line async for line in lines] == [b"a\n", b"b\n"]
        [(args, options)] = calls
        assert args == ("tail", "-n", "5")
        assert options["stdin"].name == str(path)
        assert options["stdin"].closed
        assert options["stdout"] == asyncio.subprocess.PIPE
        assert options["stderr"] == asyncio.subprocess.DEVNULL

    async def it_raises_for_a_missing_file_without_spawning(tmp_path: Path, calls: Calls) -> None:
        with pytest.raises(FileNotFoundError):
            async with read(tmp_path / "missing", "5"):
                pass
        assert calls == []

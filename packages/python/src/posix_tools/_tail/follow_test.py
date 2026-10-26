import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from posix_tools._tail.follow import follow

type Calls = list[tuple[tuple[str, ...], dict[str, Any]]]


@pytest.fixture
def calls() -> Iterator[Calls]:
    recorded: Calls = []

    @asynccontextmanager
    async def spawn(*args: str, **options: Any) -> AsyncIterator[Mock]:
        recorded.append((args, options))
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"a\n")
        stdout.feed_eof()
        yield Mock(stdout=stdout)

    with patch(f"{__package__}.follow.spawn", spawn):
        yield recorded


def describe_follow() -> None:
    async def it_runs_tail_by_name_and_yields_its_lines(calls: Calls) -> None:
        async with follow(Path("-x.log"), "+1") as lines:
            assert [line async for line in lines] == [b"a\n"]
        [(args, options)] = calls
        assert args == ("tail", "-F", "-n", "+1", "--", "-x.log")
        assert options == {
            "stdin": asyncio.subprocess.DEVNULL,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.DEVNULL,
        }

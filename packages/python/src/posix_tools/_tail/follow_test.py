import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from posix_tools._tail.follow import SCRIPT, follow

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


def closed(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return True
    return False


def describe_follow() -> None:
    async def it_runs_the_wrapper_and_yields_its_lines(calls: Calls) -> None:
        async with follow(Path("-x.log"), "+1") as lines:
            assert [line async for line in lines] == [b"a\n"]
        [(args, options)] = calls
        assert args == ("sh", "-c", SCRIPT, "sh", "+1", "-x.log")
        assert options["stdout"] == asyncio.subprocess.PIPE
        assert options["stderr"] == asyncio.subprocess.DEVNULL

    async def it_holds_the_lifetime_pipe_open_until_exit(calls: Calls) -> None:
        async with follow(Path("log"), "10"):
            [(_, options)] = calls
            lifetime = options["stdin"]
            assert not closed(lifetime)
            os.set_blocking(lifetime, False)
            with pytest.raises(BlockingIOError):
                os.read(lifetime, 1)
        assert closed(lifetime)

    async def it_closes_the_lifetime_pipe_when_the_body_raises(calls: Calls) -> None:
        with pytest.raises(ValueError, match="body"):
            async with follow(Path("log"), "10"):
                raise ValueError("body")
        [(_, options)] = calls
        assert closed(options["stdin"])

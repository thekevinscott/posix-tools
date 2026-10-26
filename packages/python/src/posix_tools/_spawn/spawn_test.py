from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.spawn import spawn

SIGTERM = 15


@pytest.fixture
def process() -> Mock:
    return Mock(pid=7, communicate=AsyncMock())


@pytest.fixture(autouse=True)
def start(process: Mock) -> Iterator[AsyncMock]:
    with patch(
        f"{__package__}.spawn.asyncio.create_subprocess_exec", autospec=True, return_value=process
    ) as m:
        yield m


@pytest.fixture(autouse=True)
def killpg() -> Iterator[Mock]:
    with patch(f"{__package__}.spawn.os.killpg", autospec=True) as m:
        yield m


def describe_spawn() -> None:
    async def it_starts_a_new_session_and_kills_the_group_on_exit(
        start: AsyncMock, killpg: Mock, process: Mock
    ) -> None:
        async with spawn("program", "arg", stdin=7, stdout=8, stderr=9) as proc:
            assert proc is process
            killpg.assert_not_called()
        start.assert_awaited_once_with(
            "program", "arg", stdin=7, stdout=8, stderr=9, start_new_session=True
        )
        killpg.assert_called_once_with(7, SIGTERM)
        process.communicate.assert_awaited_once()

    async def it_passes_no_streams_by_default(start: AsyncMock) -> None:
        async with spawn("program"):
            pass
        start.assert_awaited_once_with(
            "program", stdin=None, stdout=None, stderr=None, start_new_session=True
        )

    async def it_kills_the_group_when_the_body_raises(killpg: Mock, process: Mock) -> None:
        with pytest.raises(ValueError, match="body"):
            async with spawn("program"):
                raise ValueError("body")
        killpg.assert_called_once_with(7, SIGTERM)
        process.communicate.assert_awaited_once()

    async def it_waits_for_a_group_that_is_already_gone(killpg: Mock, process: Mock) -> None:
        killpg.side_effect = ProcessLookupError
        async with spawn("program"):
            pass
        process.communicate.assert_awaited_once()

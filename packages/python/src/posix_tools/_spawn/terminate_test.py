import asyncio
from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from posix_tools._spawn.terminate import terminate

SIGTERM = 15


@pytest.fixture(autouse=True)
def killpg() -> Iterator[Mock]:
    with patch(f"{__package__}.terminate.os.killpg", autospec=True) as m:
        yield m


def describe_terminate() -> None:
    async def it_terminates_the_started_group(killpg: Mock) -> None:
        starting = asyncio.get_running_loop().create_future()
        starting.set_result(Mock(pid=7))
        terminate(starting)
        killpg.assert_called_once_with(7, SIGTERM)

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_ignores_a_group_that_is_gone(killpg: Mock, error: type[OSError]) -> None:
        killpg.side_effect = error
        starting = asyncio.get_running_loop().create_future()
        starting.set_result(Mock(pid=7))
        terminate(starting)

    async def it_ignores_a_failed_start(killpg: Mock) -> None:
        starting = asyncio.get_running_loop().create_future()
        starting.set_exception(FileNotFoundError())
        terminate(starting)
        killpg.assert_not_called()

    async def it_ignores_a_cancelled_start(killpg: Mock) -> None:
        starting = asyncio.get_running_loop().create_future()
        starting.cancel()
        terminate(starting)
        killpg.assert_not_called()

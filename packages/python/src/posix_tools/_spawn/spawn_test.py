import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from posix_tools._spawn.spawn import GRACE, POLL, spawn

SIGKILL = 9
SIGTERM = 15


class Group:
    def __init__(self, polls: int = 0, after_kill: int = 0) -> None:
        self.polls = polls
        self.after_kill = after_kill
        self.calls: list[int] = []

    def __call__(self, _: int, signum: int) -> None:
        self.calls.append(signum)
        if signum == SIGKILL:
            self.polls = self.after_kill
        if signum == 0:
            if self.polls == 0:
                raise ProcessLookupError
            self.polls -= 1


@pytest.fixture
def process() -> Mock:
    return Mock(pid=7, communicate=AsyncMock())


@pytest.fixture(autouse=True)
def start(process: Mock) -> Iterator[AsyncMock]:
    with patch(
        f"{__package__}.spawn.asyncio.create_subprocess_exec", autospec=True, return_value=process
    ) as m:
        yield m


@pytest.fixture
def group() -> Group:
    return Group()


@pytest.fixture(autouse=True)
def killpg(group: Group) -> Iterator[Mock]:
    with patch(f"{__package__}.spawn.os.killpg", autospec=True, side_effect=group) as m:
        yield m


@pytest.fixture
def short_grace() -> Iterator[None]:
    with patch(f"{__package__}.spawn.GRACE", 0.05):
        yield


def describe_spawn() -> None:
    def it_gives_ten_seconds_of_grace_polling_every_10ms() -> None:
        assert GRACE == 10
        assert POLL == 0.01

    async def it_starts_a_new_session_and_terminates_the_group_on_exit(
        start: AsyncMock, killpg: Mock, process: Mock
    ) -> None:
        async with spawn("program", "arg", stdin=7, stdout=8, stderr=9) as proc:
            assert proc is process
            killpg.assert_not_called()
        start.assert_awaited_once_with(
            "program", "arg", stdin=7, stdout=8, stderr=9, start_new_session=True
        )
        assert killpg.call_args_list == [call(7, SIGTERM), call(7, 0)]
        process.communicate.assert_awaited_once()

    async def it_passes_no_streams_by_default(start: AsyncMock) -> None:
        async with spawn("program"):
            pass
        start.assert_awaited_once_with(
            "program", stdin=None, stdout=None, stderr=None, start_new_session=True
        )

    async def it_terminates_the_group_when_the_body_raises(group: Group, process: Mock) -> None:
        with pytest.raises(ValueError, match="body"):
            async with spawn("program"):
                raise ValueError("body")
        assert group.calls == [SIGTERM, 0]
        process.communicate.assert_awaited_once()

    async def it_waits_until_the_group_is_gone(group: Group, process: Mock) -> None:
        group.polls = 3
        async with spawn("program"):
            pass
        assert group.calls == [SIGTERM, 0, 0, 0, 0]
        process.communicate.assert_awaited_once()

    @pytest.mark.usefixtures("short_grace")
    async def it_kills_a_group_that_outlives_the_grace(group: Group, process: Mock) -> None:
        group.polls = 10_000
        async with spawn("program"):
            pass
        assert group.calls[0] == SIGTERM
        assert group.calls[-2:] == [SIGKILL, 0]
        assert set(group.calls[1:-2]) == {0}
        process.communicate.assert_awaited_once()

    @pytest.mark.usefixtures("short_grace")
    async def it_waits_until_a_killed_group_is_gone(group: Group) -> None:
        group.polls = 10_000
        group.after_kill = 3
        async with spawn("program"):
            pass
        assert group.calls[-5:] == [SIGKILL, 0, 0, 0, 0]

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_skips_the_wait_for_a_group_it_cannot_signal(
        killpg: Mock, process: Mock, error: type[OSError]
    ) -> None:
        killpg.side_effect = error
        async with spawn("program"):
            pass
        killpg.assert_called_once_with(7, SIGTERM)
        process.communicate.assert_awaited_once()

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    async def it_stops_waiting_once_the_group_cannot_be_signalled(
        killpg: Mock, group: Group, error: type[OSError]
    ) -> None:
        group.polls = 2

        def refuse_after(pgid: int, signum: int) -> None:
            try:
                group(pgid, signum)
            except ProcessLookupError:
                raise error from None

        killpg.side_effect = refuse_after
        async with spawn("program"):
            pass
        assert group.calls == [SIGTERM, 0, 0, 0]

    @pytest.mark.usefixtures("short_grace")
    async def it_ignores_a_group_gone_before_the_kill(
        killpg: Mock, group: Group, process: Mock
    ) -> None:
        group.polls = 10_000

        def gone_by_kill(pgid: int, signum: int) -> None:
            group(pgid, signum)
            if signum == SIGKILL:
                raise ProcessLookupError

        killpg.side_effect = gone_by_kill
        async with spawn("program"):
            pass
        assert group.calls[-1] == SIGKILL
        process.communicate.assert_awaited_once()

    async def it_kills_a_program_whose_start_was_cancelled(
        start: AsyncMock, killpg: Mock, process: Mock
    ) -> None:
        launched = asyncio.Event()

        async def slow_start(*_: object, **__: object) -> Mock:
            await launched.wait()
            return process

        start.side_effect = slow_start

        async def body() -> None:
            async with spawn("program"):
                pytest.fail("body ran")

        task = asyncio.ensure_future(body())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        killpg.assert_not_called()
        launched.set()
        await asyncio.sleep(0.01)
        killpg.assert_called_once_with(7, SIGTERM)

    async def it_kills_nothing_when_a_cancelled_start_fails(start: AsyncMock, killpg: Mock) -> None:
        launched = asyncio.Event()

        async def failing_start(*_: object, **__: object) -> Mock:
            await launched.wait()
            raise FileNotFoundError

        start.side_effect = failing_start

        async def body() -> None:
            async with spawn("missing"):
                pytest.fail("body ran")

        task = asyncio.ensure_future(body())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        launched.set()
        await asyncio.sleep(0.01)
        killpg.assert_not_called()

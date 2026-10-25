import asyncio
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from posix_tools._spawn.close import close

SIGINT = 2
SIGTERM = 15


@pytest.fixture(autouse=True)
def stop() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.close.stop", autospec=True) as m:
        yield m


@pytest.fixture(autouse=True)
def ended() -> Iterator[AsyncMock]:
    with patch(f"{__package__}.close.ended", autospec=True) as m:
        yield m


async def forever(*_: object) -> None:
    await asyncio.Event().wait()


def piped(data: bytes = b"", *, eof: bool = True) -> asyncio.StreamReader:
    stream = asyncio.StreamReader()
    stream.feed_data(data)
    if eof:
        stream.feed_eof()
    return stream


def options(**overrides: Any) -> dict[str, Any]:
    return {"signum": SIGTERM, "grace": 1, "linger": 0} | overrides


def describe_close() -> None:
    async def it_closes_owned_stdin() -> None:
        process = Mock(stdout=None, stderr=None)
        await close(process, (), **options())
        process.stdin.close.assert_called_once_with()

    async def it_stops_the_group_and_waits_on_drains_and_owned_pipes(
        stop: AsyncMock, ended: AsyncMock
    ) -> None:
        process = Mock(stdin=None, stdout=piped(b"out"), stderr=piped(b"err"))
        drain = asyncio.get_running_loop().create_future()
        drain.set_result(None)
        await close(process, (drain,), **options(signum=SIGINT, grace=3))
        stop.assert_awaited_once()
        assert stop.await_args is not None
        (_, waiting), kwargs = stop.await_args
        assert waiting[0] is drain
        assert len(waiting) == 3
        assert kwargs == {"signum": SIGINT, "grace": 3}
        ended.assert_not_called()

    async def it_drains_owned_pipes_until_stopped(stop: AsyncMock) -> None:
        process = Mock(stdin=None, stdout=piped(b"x" * 100_000), stderr=None)

        async def waits(_: object, waiting: tuple[asyncio.Future[None], ...], **__: object) -> None:
            await asyncio.gather(*waiting)

        stop.side_effect = waits
        await close(process, (), **options())
        assert process.stdout.at_eof()

    async def it_cancels_owned_readers_that_never_end() -> None:
        stdout = piped(eof=False)
        await asyncio.wait_for(
            close(Mock(stdin=None, stdout=stdout, stderr=None), (), **options()), 1
        )
        assert not stdout.at_eof()

    async def it_skips_stopping_when_the_group_ends_within_linger(
        stop: AsyncMock, ended: AsyncMock
    ) -> None:
        process = Mock(stdin=None, stdout=None, stderr=None)
        await close(process, (), **options(linger=1))
        ended.assert_awaited_once_with(process, ())
        stop.assert_not_called()

    async def it_treats_negative_linger_as_none(stop: AsyncMock, ended: AsyncMock) -> None:
        await close(Mock(stdin=None, stdout=None, stderr=None), (), **options(linger=-1))
        ended.assert_not_called()
        stop.assert_awaited_once()

    async def it_takes_options_by_keyword() -> None:
        with pytest.raises(TypeError):
            await close(Mock(), (), 15, 1, 0)  # type: ignore[call-arg]

    async def it_stops_when_linger_runs_out(stop: AsyncMock, ended: AsyncMock) -> None:
        ended.side_effect = forever
        await close(Mock(stdin=None, stdout=None, stderr=None), (), **options(linger=0.01))
        stop.assert_awaited_once()

    async def it_stops_when_cancelled_while_lingering(stop: AsyncMock, ended: AsyncMock) -> None:
        ended.side_effect = forever
        closing = asyncio.ensure_future(
            close(Mock(stdin=None, stdout=None, stderr=None), (), **options(linger=60))
        )
        await asyncio.sleep(0.01)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        stop.assert_awaited_once()

    async def it_finishes_stopping_through_cancels(stop: AsyncMock) -> None:
        stopped = asyncio.Event()

        async def slow(*_: object, **__: object) -> None:
            await asyncio.sleep(0.05)
            stopped.set()

        stop.side_effect = slow
        closing = asyncio.ensure_future(
            close(Mock(stdin=None, stdout=None, stderr=None), (), **options())
        )
        await asyncio.sleep(0.01)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert stopped.is_set()

import asyncio

import pytest

from posix_tools._spawn.settle import settle


async def slow(seconds: float, value: str = "done") -> str:
    await asyncio.sleep(seconds)
    return value


async def failing() -> None:
    await asyncio.sleep(0.05)
    raise ValueError("inner")


def describe_settle() -> None:
    async def it_returns_the_result() -> None:
        assert await settle(slow(0)) == "done"

    async def it_raises_the_failure() -> None:
        with pytest.raises(ValueError, match="inner"):
            await settle(failing())

    async def it_finishes_through_cancels_then_raises_the_cancel() -> None:
        inner = asyncio.ensure_future(slow(0.05))
        outer = asyncio.ensure_future(settle(inner))
        await asyncio.sleep(0)
        outer.cancel()
        await asyncio.sleep(0)
        outer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await outer
        assert inner.result() == "done"

    async def it_chains_the_failure_to_the_cancel() -> None:
        outer = asyncio.ensure_future(settle(failing()))
        await asyncio.sleep(0)
        outer.cancel()
        with pytest.raises(asyncio.CancelledError) as raised:
            await outer
        assert isinstance(raised.value.__cause__, ValueError)

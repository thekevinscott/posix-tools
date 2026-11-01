import asyncio

import pytest

from posix_tools import settle


def describe_settle() -> None:
    async def it_returns_the_result_of_a_coroutine_or_future() -> None:
        assert await settle(asyncio.sleep(0, result="done")) == "done"
        assert tuple(await settle(asyncio.gather(asyncio.sleep(0, result="a")))) == ("a",)

    async def it_propagates_failure() -> None:
        async def fail() -> None:
            raise ValueError("teardown failed")

        with pytest.raises(ValueError, match="teardown failed"):
            await settle(fail())

    async def it_finishes_through_repeated_cancels() -> None:
        finished = asyncio.Event()

        async def teardown() -> None:
            await asyncio.sleep(0.05)
            finished.set()

        task = asyncio.create_task(settle(teardown()))
        for _ in range(3):
            await asyncio.sleep(0.01)
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    async def it_propagates_cancellation_from_the_awaitable() -> None:
        async def cancelled() -> None:
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await settle(cancelled())

    async def it_keeps_a_later_failure_as_the_cancels_cause() -> None:
        async def teardown() -> None:
            await asyncio.sleep(0.03)
            raise ValueError("teardown failed")

        task = asyncio.create_task(settle(teardown()))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        assert isinstance(error.value.__cause__, ValueError)

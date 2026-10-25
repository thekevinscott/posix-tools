import asyncio

from posix_tools._spawn.within import within


def describe_within() -> None:
    async def it_is_true_when_the_awaitable_finishes_in_time() -> None:
        assert await within(1, asyncio.sleep(0))

    async def it_is_false_on_timeout() -> None:
        assert not await within(0.01, asyncio.sleep(1))

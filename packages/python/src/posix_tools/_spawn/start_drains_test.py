import asyncio
from unittest.mock import Mock

from posix_tools._spawn.start_drains import start_drains


def describe_start_drains() -> None:
    async def it_starts_only_requested_sinks() -> None:
        stdout = asyncio.StreamReader()
        stderr = asyncio.StreamReader()
        stdout.feed_data(b"out")
        stdout.feed_eof()
        process = Mock(stdout=stdout, stderr=stderr)
        received: list[bytes] = []
        errors: list[BaseException] = []
        drains = start_drains(process, (received.append, None), errors, None)
        await asyncio.gather(*drains.values())
        await asyncio.sleep(0)
        assert received == [b"out"]
        assert errors == []
        assert list(drains) == [stdout]

    async def it_records_failure_and_cancels_the_owner() -> None:
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"out")
        stdout.feed_eof()
        process = Mock(stdout=stdout, stderr=None)
        errors: list[BaseException] = []
        owner = asyncio.create_task(asyncio.Event().wait())

        def full(_chunk: bytes) -> None:
            raise OSError("full")

        drains = start_drains(process, (full, None), errors, owner)
        await asyncio.gather(*drains.values(), return_exceptions=True)
        await asyncio.sleep(0)
        assert isinstance(errors[0], OSError)
        assert owner.cancelled()

    async def it_records_failure_without_an_owner() -> None:
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"out")
        stdout.feed_eof()
        process = Mock(stdout=stdout, stderr=None)
        errors: list[BaseException] = []

        def full(_chunk: bytes) -> None:
            raise OSError("full")

        drains = start_drains(process, (full, None), errors, None)
        await asyncio.gather(*drains.values(), return_exceptions=True)
        await asyncio.sleep(0)
        assert isinstance(errors[0], OSError)

    async def it_ignores_cancelled_drains() -> None:
        stdout = asyncio.StreamReader()
        process = Mock(stdout=stdout, stderr=None)
        errors: list[BaseException] = []
        drains = start_drains(process, (lambda _: None, None), errors, None)
        task = drains[stdout]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)
        assert errors == []

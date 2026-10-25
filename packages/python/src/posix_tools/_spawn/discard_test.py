import asyncio

from posix_tools._spawn.discard import CHUNK, discard


def describe_discard() -> None:
    async def it_reads_to_the_end() -> None:
        stream = asyncio.StreamReader()
        stream.feed_data(b"x" * (CHUNK * 3 + 1))
        stream.feed_eof()
        await discard(stream)
        assert stream.at_eof()

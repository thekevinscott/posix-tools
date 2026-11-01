import asyncio

from posix_tools._spawn.drain import drain


def describe_drain() -> None:
    async def it_delivers_each_chunk_to_the_sink() -> None:
        reader = asyncio.StreamReader()
        received: list[bytes] = []
        reader.feed_data(b"x" * 65537)
        reader.feed_eof()
        await drain(reader, received.append)
        assert received == [b"x" * 65536, b"x"]

    async def it_discards_chunks_without_a_sink() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"discard")
        reader.feed_eof()
        await drain(reader, None)
        assert reader.at_eof()

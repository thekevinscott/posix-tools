import asyncio

import pytest

from posix_tools._tail.lines import Lines


def stream(*chunks: bytes, eof: bool = True) -> asyncio.StreamReader:
    reader = asyncio.StreamReader(limit=8)
    for chunk in chunks:
        reader.feed_data(chunk)
    if eof:
        reader.feed_eof()
    return reader


def describe_lines() -> None:
    async def it_yields_each_line_with_its_newline_then_stops() -> None:
        assert [line async for line in Lines(stream(b"a\nb\n", b"c\n"))] == [b"a\n", b"b\n", b"c\n"]

    async def it_yields_a_final_unterminated_line_as_is() -> None:
        assert [line async for line in Lines(stream(b"a\nlast"))] == [b"a\n", b"last"]

    async def it_stops_at_once_on_an_empty_stream() -> None:
        with pytest.raises(StopAsyncIteration):
            await anext(Lines(stream()))

    @pytest.mark.parametrize("eof", [True, False])
    async def it_joins_a_line_longer_than_the_buffer(eof: bool) -> None:
        lines = Lines(stream(b"x" * 30 + b"\nnext\n", eof=eof))
        assert await anext(lines) == b"x" * 30 + b"\n"
        assert await anext(lines) == b"next\n"

    async def it_joins_an_unterminated_line_longer_than_the_buffer() -> None:
        assert [line async for line in Lines(stream(b"y" * 30))] == [b"y" * 30]

    async def it_keeps_the_half_read_line_across_a_cancelled_read() -> None:
        reader = stream(b"z" * 20, eof=False)
        lines = Lines(reader)
        reading = asyncio.ensure_future(anext(lines))
        await asyncio.sleep(0)
        reading.cancel()
        with pytest.raises(asyncio.CancelledError):
            await reading
        reader.feed_data(b"z\n")
        assert await anext(lines) == b"z" * 21 + b"\n"

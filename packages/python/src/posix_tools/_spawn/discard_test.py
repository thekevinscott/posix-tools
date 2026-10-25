from unittest.mock import AsyncMock, Mock, call

from posix_tools._spawn.discard import discard


def describe_discard() -> None:
    async def it_reads_in_64k_chunks_to_the_end() -> None:
        stream = Mock(read=AsyncMock(side_effect=[b"a", b"b", b""]))
        await discard(stream)
        assert stream.read.await_args_list == [call(65536)] * 3

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import pytest

from posix_tools._tail.tail import tail

type Calls = list[tuple[str, Path, str]]
type Opener = Callable[[Path, str], AbstractAsyncContextManager[AsyncIterator[bytes]]]


@pytest.fixture(autouse=True)
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[Calls]:
    recorded: Calls = []

    def opener(kind: str) -> Opener:
        @asynccontextmanager
        async def open_(path: Path, count: str) -> AsyncIterator[AsyncIterator[bytes]]:
            recorded.append((kind, path, count))

            async def lines() -> AsyncIterator[bytes]:
                yield b"a\n"
                yield b"b\n"

            yield lines()

        return open_

    monkeypatch.setattr(f"{__package__}.tail.read", opener("read"))
    monkeypatch.setattr(f"{__package__}.tail.follow", opener("follow"))
    yield recorded


def describe_tail() -> None:
    async def it_reads_the_last_ten_lines_by_default(calls: Calls) -> None:
        async with tail("app.log") as lines:
            assert [line async for line in lines] == [b"a\n", b"b\n"]
        assert calls == [("read", Path("app.log"), "10")]

    @pytest.mark.parametrize(("n", "count"), [(3, "3"), (0, "0"), (None, "+1")])
    async def it_reads_from_n_lines_before_the_end(calls: Calls, n: int | None, count: str) -> None:
        async with tail("app.log", n=n) as lines:
            assert [line async for line in lines] == [b"a\n", b"b\n"]
        assert calls == [("read", Path("app.log"), count)]

    async def it_follows_when_asked(calls: Calls) -> None:
        async with tail(Path("app.log"), n=None, follow=True) as lines:
            assert await anext(lines) == b"a\n"
        assert calls == [("follow", Path("app.log"), "+1")]

    async def it_returns_every_line_when_awaited(calls: Calls) -> None:
        assert await tail("app.log", n=1) == [b"a\n", b"b\n"]
        assert calls == [("read", Path("app.log"), "1")]

    async def it_refuses_to_await_a_follow(calls: Calls) -> None:
        with pytest.raises(TypeError, match="never ends"):
            await tail("app.log", follow=True)
        assert calls == []

    def it_rejects_a_negative_n() -> None:
        with pytest.raises(ValueError, match="n must be"):
            tail("app.log", n=-1)

    async def it_passes_body_errors_through() -> None:
        with pytest.raises(KeyError):
            async with tail("app.log"):
                raise KeyError("body")

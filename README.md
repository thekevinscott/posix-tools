# posix-tools

Python APIs that wrap native POSIX tools.

## Installation

```bash
pip install posix-tools
```

Requires Python 3.12+ on a POSIX system (Linux or macOS).

## `spawn`

Run a program, and know it and everything it started are gone when the block exits.

```python
import asyncio

from posix_tools import spawn


async def main() -> None:
    async with spawn("sleep", "60") as proc:
        await asyncio.sleep(1)
    # sleep, and anything it started, is gone.


asyncio.run(main())
```

`spawn(program, *args, stdin=, stdout=, stderr=)` yields the `asyncio.subprocess.Process`.

- **Stopping.** Leaving the block, by normal exit, error, or cancel, sends SIGTERM to the program and everything it started, then waits for the program to exit. A cancel that lands while the program is starting still stops it.

## `tail`

Read the end of a file, or follow it as it grows, the way `tail` and `tail -F` do.

```python
from posix_tools import tail


async def main() -> None:
    # Last line. Awaiting reads until tail exits.
    [last] = await tail("app.log", n=1)

    # Live. The stream never ends; leaving the block stops tail.
    async with tail("app.log", follow=True) as lines:
        async for line in lines:
            print(line)
```

`tail(path, n=10, follow=False)` yields an async iterator of `bytes` lines, each with its trailing `\n`.

Use it with `async with` to stream lines, or `await` it to get them all as a `list[bytes]`. Awaiting with `follow=True` raises `TypeError`, since that stream never ends.

- **`n`.** How many lines from the end to start with. `n=None` starts from the top of the file.
- **`follow`.** Keep reading as the file grows. It keeps going if the file is rotated or replaced, and waits if the file does not exist yet. Without `follow`, a missing file raises `FileNotFoundError`.
- **Long lines.** A line longer than the stream buffer still arrives whole.
- **Stopping.** Leaving the block, by `break`, error, or cancel, stops `tail` and reaps it. If your process dies, `tail` dies with it.
- **Cancel-safe.** A cancelled `anext()` keeps the half-read line for the next call.

## Rules

- Nothing here imports botbox. botbox depends on posix-tools, never the reverse.

## License

MIT

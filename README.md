# posix-tools

Python APIs that wrap native POSIX tools.

## Installation

```bash
pip install posix-tools
```

Requires Python 3.12+ on a POSIX system (Linux or macOS). No runtime dependencies.

## `posix_tools.process`

Run a program as its own process group, and know the whole group is gone when the block exits, even if the task is cancelled.

```python
import asyncio

from posix_tools import process


async def main() -> None:
    async with process("sleep", "60") as proc:
        await asyncio.sleep(1)
    # sleep's process group has been stopped and reaped.


asyncio.run(main())
```

`child(program, *args, stdin=, stdout=, stderr=, signum=SIGTERM, grace=10, linger=0, drains=())` yields the `asyncio.subprocess.Process`.

- **Start.** The program leads a new process group. Startup is shielded from cancellation; a start that gets cancelled still cleans up what it launched.
- **Exit.** On normal exit, error, or cancel, the group gets `signum`, then SIGKILL after `grace` seconds. Cleanup then drains owned pipes and reaps. It runs to the end through further cancels.
- **`linger`.** On normal exit only, wait this many seconds for the group to finish by itself before signalling.
- **Pipes.** Pipes `child()` creates (`asyncio.subprocess.PIPE`) are owned: the body must stop reading them before it exits, and cleanup drains them. Descriptors you pass in, such as an open file, are borrowed and left open.

## `posix_tools.tail`

Follow a file the way `tail -F` does, as an async iterator of lines.

```python
from posix_tools import tail


async def main() -> None:
    async with tail("app.log") as lines:
        async for line in lines:
            print(line)
```

`tail(path)` yields an async iterator of `bytes` lines, each with its trailing `\n`.

- **From the start.** It reads the whole file, then waits for new lines.
- **Follows the name.** It keeps going if the file is rotated or replaced, and waits if the file does not exist yet.
- **Long lines.** A line longer than the stream buffer still arrives whole.
- **Stopping.** Leaving the block, by `break`, error, or cancel, stops `tail` and reaps it. If your process dies, `tail` dies with it.
- **Cancel-safe.** A cancelled `anext()` keeps the half-read line for the next call.

## Rules

- Standard library only.
- Nothing here imports botbox. botbox depends on posix-tools, never the reverse.

## License

MIT

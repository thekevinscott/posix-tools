# posix-tools

Python APIs that wrap native POSIX tools.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

Pre-release. The code is moving here from [botbox](https://github.com/thekevinscott/botbox), its only consumer so far. Nothing is on PyPI yet.

## Installation

```bash
pip install posix-tools
```

Requires Python 3.12+ on a POSIX system (Linux or macOS). No runtime dependencies.

## `posix_tools.process`

Run a program as its own process group, and know the whole group is gone when the block exits, even if the task is cancelled.

```python
import asyncio

from posix_tools.process import child


async def main() -> None:
    async with child("sleep", "60") as proc:
        await asyncio.sleep(1)
    # sleep's process group has been stopped and reaped.


asyncio.run(main())
```

`child(program, *args, stdin=, stdout=, stderr=, signum=SIGTERM, grace=10, linger=0, drains=())` yields the `asyncio.subprocess.Process`.

- **Start.** The program leads a new process group. Startup is shielded from cancellation; a start that gets cancelled still cleans up what it launched.
- **Exit.** On normal exit, error, or cancel, the group gets `signum`, then SIGKILL after `grace` seconds. Cleanup then drains owned pipes and reaps. It runs to the end through further cancels.
- **`linger`.** On normal exit only, wait this many seconds for the group to finish by itself before signalling.
- **Pipes.** Pipes `child()` creates (`asyncio.subprocess.PIPE`) are owned: the body must stop reading them before it exits, and cleanup drains them. Descriptors you pass in, such as an open file, are borrowed and left open.

Known limit: a grandchild that calls `setsid()` leaves the group but can keep a pipe open. Cleanup then waits up to `linger + 2 * grace` and the escaped process leaks ([botbox#184](https://github.com/thekevinscott/botbox/issues/184)).

## Rules

- Standard library only.
- Nothing here imports botbox. botbox depends on posix-tools, never the reverse.

## License

MIT

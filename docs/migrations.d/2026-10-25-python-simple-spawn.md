## Summary

`spawn()` drops every option beyond the program, its arguments and its three streams. They were never asked for. Exit always sends SIGTERM to the group, then SIGKILL after 10 seconds.

## Required changes

```python
# Before
async with spawn("prog", signum=signal.SIGKILL, grace=2, linger=1, drains=(eof,)) as proc:
    ...

# After
async with spawn("prog") as proc:
    ...
await asyncio.wait_for(eof, 1)  # wait on your own readers yourself
```

## Deprecations removed

None.

## Behavior changes without code changes

- Pipes created with `asyncio.subprocess.PIPE` are no longer read to EOF on exit. Unread output is dropped.
- A setsid() escapee holding a pipe no longer stalls cleanup.

## Verification

```bash
python -c "import inspect, posix_tools; print(inspect.signature(posix_tools.spawn))"
# (program: str, *args: str, stdin: ... = None, stdout: ... = None, stderr: ... = None) -> ...
```

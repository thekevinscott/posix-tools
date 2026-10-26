## Summary

`spawn()` no longer follows SIGTERM with SIGKILL. A program that ignores SIGTERM keeps the block waiting.

## Required changes

None in code. If your program may ignore SIGTERM, kill it yourself before leaving the block.

## Deprecations removed

None.

## Behavior changes without code changes

- No SIGKILL after 10 seconds.
- If the owner process is killed outright, the group is not cleaned up. Use a supervisor such as systemd for that.
- Unread output on `PIPE` streams is read and discarded on exit.

## Verification

```bash
python -c "import importlib.util as u; print(u.find_spec('psutil'))"
# None in a fresh environment with only posix-tools installed
```

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager

# Our end of the pipe closes when we die, however we die. The watcher reads EOF and kills the group.
WATCHER = 'read -r _; kill -KILL -"$1"'


@contextmanager
def watch(pgid: int) -> Iterator[None]:
    lifetime, owner = os.pipe()
    try:
        try:
            watcher = subprocess.Popen(
                ("sh", "-c", WATCHER, "sh", str(pgid)),
                stdin=lifetime,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        finally:
            os.close(lifetime)
        try:
            yield
        finally:
            # Stop it before the group goes, so a later EOF can't signal a reused pgid.
            watcher.kill()
            watcher.wait()
    finally:
        os.close(owner)

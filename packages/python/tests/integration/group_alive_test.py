import os
import signal
import subprocess
import time

import psutil

from posix_tools._spawn.group_alive import group_alive


def wait_for_zombie(pid: int) -> None:
    deadline = time.monotonic() + 5
    while psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
        assert time.monotonic() < deadline
        time.sleep(0.01)


def describe_group_alive() -> None:
    def it_sees_a_running_group() -> None:
        leader = subprocess.Popen(["sleep", "60"], start_new_session=True)
        try:
            assert group_alive(leader.pid)
        finally:
            leader.kill()
            leader.wait()

    def it_ignores_an_unreaped_zombie() -> None:
        leader = subprocess.Popen(["sleep", "60"], start_new_session=True)
        leader.send_signal(signal.SIGKILL)
        try:
            wait_for_zombie(leader.pid)
            assert not group_alive(leader.pid)
        finally:
            leader.wait()

    def it_sees_a_member_that_outlives_its_leader() -> None:
        leader = subprocess.Popen(
            ["sh", "-c", "sleep 60 & echo $!"], stdout=subprocess.PIPE, start_new_session=True
        )
        assert leader.stdout is not None
        orphan = int(leader.stdout.readline())
        leader.stdout.close()
        leader.wait()
        try:
            assert group_alive(leader.pid)
        finally:
            os.kill(orphan, signal.SIGKILL)

**Fixed** `spawn()` waits on exit until every process in the group is gone, sending SIGKILL to any still running after 10 seconds.

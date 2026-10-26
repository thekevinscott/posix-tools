**Changed** `spawn()` no longer waits for the whole group on exit, which hung when a group member was never reaped. It sends SIGTERM to the group and waits for the program alone, as before 0.0.9.

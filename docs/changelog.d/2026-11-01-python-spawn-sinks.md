Added callable stdout and stderr sinks to `spawn`. Each pipe chunk is delivered as it is read without buffering; sink failures stop and reap the process while the other sink drains pending output.

Added `settle(coro)` to finish an awaitable through repeated caller cancellations. A cancellation is raised after cleanup completes, with any cleanup failure preserved as its cause.

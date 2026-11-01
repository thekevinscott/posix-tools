from collections.abc import Callable
from typing import IO, Any

type Stream = int | IO[Any] | None
type Sink = Callable[[bytes], object]

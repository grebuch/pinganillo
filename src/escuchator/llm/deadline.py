"""Bounded waiting for slow network calls.

Python cannot safely kill a thread that is blocked on a socket, so a timeout
here means "stop waiting", not "cancel the request". To avoid piling up
requests, a new call is refused while the previous worker is still alive.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class DeadlineCall:
    """At most one in-flight worker; late results are never reused."""

    def __init__(self, timeout: float = 45, progress: Callable[[int, float], None] | None = None) -> None:
        self.timeout, self.progress = timeout, progress
        self.worker: threading.Thread | None = None
        self.lock = threading.Lock()

    @property
    def busy(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def call(self, target: Callable[[], T]) -> T:
        with self.lock:
            if self.busy:
                raise RuntimeError(
                    "A previous AI request is still open; not starting another one in parallel."
                )
            result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

            def run() -> None:
                try:
                    result.put((True, target()))
                except Exception as exc:
                    result.put((False, exc))

            self.worker = threading.Thread(target=run, daemon=True, name="ai-request")
            self.worker.start()
        start = time.monotonic()
        while True:
            remaining = self.timeout - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError(
                    f"The AI did not finish within {self.timeout:.0f} s. Only the analysis is paused; "
                    "capture and transcription keep running."
                )
            try:
                ok, value = result.get(timeout=min(1, remaining))
            except queue.Empty:
                if self.progress:
                    self.progress(int(time.monotonic() - start), self.timeout)
                continue
            if not ok:
                assert isinstance(value, BaseException)
                raise value
            return value  # type: ignore[return-value]

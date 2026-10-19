import threading

import pytest

from pinganillo.llm.deadline import DeadlineCall


def test_timeout_then_no_parallel_request_then_recovers():
    release = threading.Event()
    guard = DeadlineCall(timeout=0.03)
    try:
        with pytest.raises(TimeoutError):
            guard.call(lambda: release.wait(2))
        with pytest.raises(RuntimeError):
            guard.call(lambda: "must not start")
    finally:
        release.set()
        guard.worker.join(2)
    assert guard.call(lambda: "new result") == "new result"


def test_worker_exception_is_re_raised():
    guard = DeadlineCall(timeout=1)

    def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        guard.call(fail)

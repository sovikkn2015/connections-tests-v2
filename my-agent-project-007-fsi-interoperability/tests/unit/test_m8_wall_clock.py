"""Task 13 -- Wall-clock ceiling + slow alert exactly-once."""

from m8_pipeline_engine.graph import _wall_clock_check


def test_wall_clock_check_not_exceeded():
    import time
    start = time.perf_counter()
    assert _wall_clock_check(start, max_seconds=3600) is False


def test_wall_clock_check_exceeded():
    import time
    start = time.perf_counter() - 10_000
    assert _wall_clock_check(start, max_seconds=1) is True

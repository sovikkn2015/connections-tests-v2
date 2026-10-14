"""Task 11 -- Hypothesis determinism, CI budget max_examples=20."""

import os
import pytest
from hypothesis import given, settings, strategies as st

from m8_pipeline_engine.graph import run
from tests.fixtures.m8_fixtures import make_initial_state

CI_MAX = 20
LOCAL_MAX = 50
MAX = CI_MAX if os.environ.get("CI") == "1" else LOCAL_MAX


@given(seed=st.integers(min_value=1, max_value=100))
@settings(max_examples=MAX, deadline=5000)
def test_pipeline_run_is_deterministic_by_status(seed):
    """Running the pipeline twice with identical inputs yields identical status."""
    import uuid
    state_a = make_initial_state(thread_id=f"thread-det-{seed:04d}-aaaa")
    state_b = make_initial_state(thread_id=f"thread-det-{seed:04d}-bbbb")
    # Same routing_decision; different thread_ids only
    state_b["routing_decision"] = state_a["routing_decision"]
    r1 = run(state_a, state_a["thread_id"])
    r2 = run(state_b, state_b["thread_id"])
    assert r1.status == r2.status

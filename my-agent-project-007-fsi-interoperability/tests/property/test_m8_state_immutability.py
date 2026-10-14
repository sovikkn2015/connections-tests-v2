"""Task 11 -- AC1.6 state immutability."""

import copy

from m8_pipeline_engine.graph import run
from tests.fixtures.m8_fixtures import make_initial_state


def test_run_does_not_mutate_initial_state():
    state = make_initial_state()
    before = copy.deepcopy({k: v for k, v in state.items() if k != "routing_decision"})
    run(state, state["thread_id"])
    after = {k: v for k, v in state.items() if k != "routing_decision"}
    assert before == after

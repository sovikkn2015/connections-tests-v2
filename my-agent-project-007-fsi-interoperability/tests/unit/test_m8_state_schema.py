"""Task 4 -- State schema + cost-basis invariant walk."""

import pytest

from m8_pipeline_engine.graph import (
    _validate_initial_state,
    _validate_state_invariants,
    _validate_thread_id,
)
from tests.fixtures.m8_fixtures import make_initial_state


def test_required_keys_enforced():
    with pytest.raises(ValueError, match="incomplete_initial_state"):
        _validate_initial_state({})


def test_not_a_pipeline_intent():
    state = make_initial_state()
    # Mutate routing_decision.selected_target.kind (via model_copy)
    from m9_intent_router.models import RoutingDecision
    rd = state["routing_decision"]
    bad_rd = rd.model_copy(update={"selected_target": rd.selected_target.model_copy(update={"kind": "tool", "name": "t.x"})})
    state["routing_decision"] = bad_rd
    with pytest.raises(ValueError, match="not_a_pipeline_intent"):
        _validate_initial_state(state)


def test_unknown_pipeline_name():
    state = make_initial_state()
    rd = state["routing_decision"]
    bad_rd = rd.model_copy(update={"selected_target": rd.selected_target.model_copy(update={"name": "m8.bogus"})})
    state["routing_decision"] = bad_rd
    with pytest.raises(ValueError, match="unknown_pipeline_name"):
        _validate_initial_state(state)


def test_valid_initial_state_passes():
    state = make_initial_state()
    _validate_initial_state(state)  # no raise


def test_thread_id_pattern():
    _validate_thread_id("thread-" + "a" * 10)
    with pytest.raises(ValueError, match="invalid_thread_id"):
        _validate_thread_id("x")  # too short
    with pytest.raises(ValueError, match="invalid_thread_id"):
        _validate_thread_id("Bad_Upper_12345678")


def test_cost_basis_invariant_walks_tax_lots():
    state = make_initial_state()
    # Craft a holding-like dict with one tax_lot missing cost_basis_method
    state["prior_holdings"] = [
        {"canonical_id": "h1", "tax_lots": [{"lot_id": "l1", "cost_basis_method": None}]}
    ]
    rc = _validate_state_invariants(state)
    assert rc == "m8_invalid_state"


def test_cost_basis_invariant_passes_when_set():
    state = make_initial_state()
    state["prior_holdings"] = [
        {"canonical_id": "h1", "tax_lots": [{"lot_id": "l1", "cost_basis_method": "specific_lot"}]}
    ]
    rc = _validate_state_invariants(state)
    assert rc is None

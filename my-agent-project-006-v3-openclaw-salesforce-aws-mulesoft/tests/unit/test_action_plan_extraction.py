"""Unit tests for openclaw.orchestration.coordinator._extract_action_plan.

The agentcore_server envelope relies on this helper to lift a structured
ActionPlan from the action_specialist's final text so the frontend
InlineActionCard can render it. These tests lock the contract.
"""

from __future__ import annotations

import json

from openclaw.orchestration.coordinator import _extract_action_plan


def test_extracts_fenced_json_block() -> None:
    text = """
    Here is the plan.

    ```json
    {
      "action_plan": {
        "plan_id": "plan-9d3a71fc",
        "action_type": "submit_order",
        "summary": "Trim NVDA from 14.2% to 9.5%",
        "client_household": "Vance-A",
        "notional_usd": 300003,
        "requires_dual_auth": false
      },
      "gate_trace": [],
      "final_status": "PENDING_APPROVAL"
    }
    ```
    """
    plan, raw = _extract_action_plan(text)
    assert plan is not None
    assert plan["plan_id"] == "plan-9d3a71fc"
    assert plan["action_type"] == "submit_order"
    assert plan["summary"] == "Trim NVDA from 14.2% to 9.5%"
    assert plan["client_household"] == "Vance-A"
    assert plan["notional_usd"] == 300003
    assert plan["requires_dual_auth"] is False
    # plan_hash is deterministic — sha256 of canonicalized payload
    assert isinstance(plan["plan_hash"], str)
    assert len(plan["plan_hash"]) == 64
    assert raw is not None
    assert raw["final_status"] == "PENDING_APPROVAL"


def test_extracts_unfenced_trailing_json() -> None:
    text = (
        "The RM asked for a trim. I built an ActionPlan below.\n\n"
        + json.dumps(
            {
                "action_plan": {
                    "action_type": "initiate_wire",
                    "summary": "Wire $120K",
                    "client_household": "Kapoor",
                    "notional_usd": 120_000,
                },
                "final_status": "PENDING_APPROVAL",
            }
        )
    )
    plan, raw = _extract_action_plan(text)
    assert plan is not None
    # action_type normalised
    assert plan["action_type"] == "initiate_wire"
    # wire > $100K triggers dual-auth even if LLM didn't include the flag
    assert plan["requires_dual_auth"] is True
    assert raw is not None


def test_derives_dual_auth_from_trade_threshold() -> None:
    text = json.dumps(
        {
            "action_plan": {
                "action_type": "submit_order",
                "notional_usd": 600_000,
                "client_household": "household-1",
            }
        }
    )
    plan, _ = _extract_action_plan(text)
    assert plan is not None
    assert plan["requires_dual_auth"] is True


def test_returns_none_when_no_json_present() -> None:
    text = "The compliance specialist blocked this trade. No plan was constructed."
    plan, raw = _extract_action_plan(text)
    assert plan is None
    assert raw is None


def test_normalises_unknown_action_type_to_submit_order() -> None:
    text = json.dumps(
        {
            "action_plan": {
                "action_type": "purchase_bitcoin",
                "notional_usd": 1000,
                "client_household": "h",
            }
        }
    )
    plan, _ = _extract_action_plan(text)
    assert plan is not None
    assert plan["action_type"] == "submit_order"


def test_generates_plan_id_when_missing() -> None:
    text = json.dumps({"action_plan": {"action_type": "submit_order"}})
    plan, _ = _extract_action_plan(text)
    assert plan is not None
    assert plan["plan_id"].startswith("plan-")
    assert len(plan["plan_id"]) == len("plan-") + 12


def test_plan_hash_stable_for_same_canonical_payload() -> None:
    text_a = json.dumps(
        {
            "action_plan": {
                "plan_id": "plan-fixed",
                "action_type": "submit_order",
                "client_household": "h",
                "notional_usd": 100,
            }
        }
    )
    text_b = json.dumps(
        {
            "action_plan": {
                "notional_usd": 100,
                "client_household": "h",
                "action_type": "submit_order",
                "plan_id": "plan-fixed",
                "extra_field": "ignored",
            }
        }
    )
    plan_a, _ = _extract_action_plan(text_a)
    plan_b, _ = _extract_action_plan(text_b)
    assert plan_a is not None and plan_b is not None
    assert plan_a["plan_hash"] == plan_b["plan_hash"]

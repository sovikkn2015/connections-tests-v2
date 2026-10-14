"""
M9 Task 3 -- Intent taxonomy + dispatch table + invariants A1-A19.

AC2.1-2.9 + A1-A19.
"""

from __future__ import annotations

import re
from types import MappingProxyType

import pytest

from m9_intent_router.errors import VALID_REASON_CODES
from m9_intent_router.taxonomy import (
    TAXONOMY_DISPATCH,
    IntentCategory,
    SelectedTarget,
    build_tool_schema,
)


def test_ac2_1_eleven_members():
    assert len(IntentCategory) == 11


def test_ac2_1_exact_members():
    names = {e.name for e in IntentCategory}
    assert names == {
        "RESEARCH_MEETING_PREP",
        "RESEARCH_PORTFOLIO_REVIEW",
        "RESEARCH_MARKET_QUERY",
        "RESEARCH_HOUSEHOLD_SUMMARY",
        "CLIENT_DATA_LOOKUP",
        "CLIENT_GOAL_TRACKING",
        "CLIENT_PLAN_SUMMARY",
        "TRADE_INQUIRY",
        "COMPLIANCE_QUESTION",
        "ESCALATE_TO_HUMAN",
        "UNSUPPORTED",
    }


def test_ac2_1_no_old_client_household_summary():
    """Fix 11 -- CLIENT_HOUSEHOLD_SUMMARY renamed to RESEARCH_HOUSEHOLD_SUMMARY."""
    assert "CLIENT_HOUSEHOLD_SUMMARY" not in [e.name for e in IntentCategory]
    assert (
        IntentCategory.RESEARCH_HOUSEHOLD_SUMMARY.value
        == "research.household_summary"
    )


def test_ac2_2_dispatch_is_mapping_proxy():
    """A12 invariant."""
    assert isinstance(TAXONOMY_DISPATCH, MappingProxyType)


def test_ac2_2_dispatch_cardinality():
    """A2 invariant."""
    assert len(TAXONOMY_DISPATCH) == 11
    assert set(TAXONOMY_DISPATCH.keys()) == set(IntentCategory)


def test_ac2_3_compliance_question_escalates():
    target = TAXONOMY_DISPATCH[IntentCategory.COMPLIANCE_QUESTION]
    assert target.kind == "escalate"
    assert target.name == "compliance_specialist"


def test_ac2_4_escalate_to_human():
    target = TAXONOMY_DISPATCH[IntentCategory.ESCALATE_TO_HUMAN]
    assert target.kind == "escalate"
    assert target.name == "human_specialist"


def test_ac2_5_unsupported_escalates():
    target = TAXONOMY_DISPATCH[IntentCategory.UNSUPPORTED]
    assert target.kind == "escalate"
    assert target.name == "human_specialist"


def test_ac2_6_research_routes_to_pipeline():
    research = [e for e in IntentCategory if e.value.startswith("research.")]
    for e in research:
        assert TAXONOMY_DISPATCH[e].kind == "pipeline"


def test_ac2_8_alphabetical_ordering():
    """A13 invariant."""
    values = [e.value for e in IntentCategory]
    assert values == sorted(values)


def test_ac2_9_prefix_kind_consistency():
    """A19 invariant (Fix 11)."""
    for intent, target in TAXONOMY_DISPATCH.items():
        value = intent.value
        if target.kind == "pipeline":
            assert value.startswith("research.")
        elif target.kind == "tool":
            assert value.startswith("client.") or value.startswith("trade.")
        elif target.kind == "escalate":
            assert (
                value.startswith("compliance.")
                or value == "escalate_to_human"
                or value == "unsupported"
            )


def test_a4_rule14_invariant():
    """Rule 14 -- M9 NEVER LLM-answers compliance."""
    assert (
        TAXONOMY_DISPATCH[IntentCategory.COMPLIANCE_QUESTION].kind == "escalate"
    )


def test_a7_pipeline_names_match_m8_contract():
    pattern = re.compile(r"^m8\.research_(pipeline_[1-3]|single_tool)$")
    for target in TAXONOMY_DISPATCH.values():
        if target.kind == "pipeline":
            assert pattern.match(target.name), (
                f"pipeline name {target.name!r} does not match M8 contract"
            )


def test_a8_tool_names_have_namespace():
    for target in TAXONOMY_DISPATCH.values():
        if target.kind == "tool":
            assert "." in target.name


def test_a9_a10_a11_bucket_counts():
    pipelines = [t for t in TAXONOMY_DISPATCH.values() if t.kind == "pipeline"]
    tools = [t for t in TAXONOMY_DISPATCH.values() if t.kind == "tool"]
    escalates = [t for t in TAXONOMY_DISPATCH.values() if t.kind == "escalate"]
    assert len(pipelines) == 4
    assert len(tools) == 4
    assert len(escalates) == 3


def test_a15_reason_codes_thirteen():
    assert isinstance(VALID_REASON_CODES, frozenset)
    assert len(VALID_REASON_CODES) == 13


def test_a16_no_mnpi_leak_in_reason_codes():
    for code in VALID_REASON_CODES:
        for banned in ("ssn", "routing", "bank", "account_number"):
            assert banned not in code


def test_a18_no_empty_target_name():
    for target in TAXONOMY_DISPATCH.values():
        assert len(target.name) > 0


def test_selected_target_rejects_unknown_kind():
    with pytest.raises(Exception):  # pydantic ValidationError
        SelectedTarget(kind="weird", name="x")


def test_selected_target_rejects_empty_name():
    with pytest.raises(Exception):
        SelectedTarget(kind="tool", name="")


def test_selected_target_frozen():
    st = SelectedTarget(kind="tool", name="sfdc.fetch_client")
    with pytest.raises(Exception):
        st.name = "other"  # type: ignore[misc]


def test_taxonomy_dispatch_is_immutable():
    """A12 runtime enforcement -- mutation raises TypeError."""
    with pytest.raises(TypeError):
        TAXONOMY_DISPATCH[IntentCategory.TRADE_INQUIRY] = SelectedTarget(  # type: ignore[index]
            kind="tool", name="x.y"
        )


def test_build_tool_schema_has_11_enum_values():
    schema = build_tool_schema()
    enum_values = schema["tools"][0]["toolSpec"]["inputSchema"]["json"][
        "properties"
    ]["intent"]["enum"]
    assert len(enum_values) == 11
    assert "research.household_summary" in enum_values
    assert "client.household_summary" not in enum_values


def test_build_tool_schema_forces_tool_choice():
    schema = build_tool_schema()
    assert schema["toolChoice"] == {"tool": {"name": "routing_decision"}}
    assert (
        schema["tools"][0]["toolSpec"]["inputSchema"]["json"][
            "additionalProperties"
        ]
        is False
    )

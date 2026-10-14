"""
M9 Intent Router -- 11-value FSI intent taxonomy + dispatch table.

Exposes:
- IntentCategory: str, Enum -- exactly 11 members, alphabetically ordered
  by string value (AC2.1, AC2.8).
- SelectedTarget: Pydantic model with kind in {pipeline, tool, escalate}
  and a non-empty name (AC2.2, A3, A18).
- TAXONOMY_DISPATCH: types.MappingProxyType[IntentCategory, SelectedTarget]
  -- immutable dispatch table, exactly 11 entries (AC2.2, A2, A12).
- build_tool_schema(): emits the Bedrock Converse toolConfig JSON shape
  for LLM function calling (AC3.2).
- _validate_taxonomy(): invariants A1-A19, asserted at import time.

See `.kiro/specs/m9-intent-router.md` FSI Intent Taxonomy + Appendix A.
"""

from __future__ import annotations

import re
from enum import Enum
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntentCategory(str, Enum):
    """11-value closed FSI intent taxonomy (AC2.1, AC2.8).

    Members are alphabetically ordered by string value for
    deterministic tie-break (AC10.3). v0.2.0 renames
    CLIENT_HOUSEHOLD_SUMMARY -> RESEARCH_HOUSEHOLD_SUMMARY (Fix 11).
    """

    # Alphabetical by string value.
    CLIENT_DATA_LOOKUP = "client.data_lookup"
    CLIENT_GOAL_TRACKING = "client.goal_tracking"
    CLIENT_PLAN_SUMMARY = "client.plan_summary"
    COMPLIANCE_QUESTION = "compliance.question"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    RESEARCH_HOUSEHOLD_SUMMARY = "research.household_summary"
    RESEARCH_MARKET_QUERY = "research.market_query"
    RESEARCH_MEETING_PREP = "research.meeting_prep"
    RESEARCH_PORTFOLIO_REVIEW = "research.portfolio_review"
    TRADE_INQUIRY = "trade.inquiry"
    UNSUPPORTED = "unsupported"


class SelectedTarget(BaseModel):
    """Dispatch target: pipeline | tool | escalate (A3, A18)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["pipeline", "tool", "escalate"]
    name: str = Field(min_length=1)


# Dispatch table -- every enum member maps to exactly one target.
# Names matching pipeline-kind pattern m8.research_* are PENDING-CONFIRM-WITH-M8
# (Known Blockers row 5). Names matching m6.composed_goal_tracking are
# PENDING-CONFIRM-WITH-M6 (Known Blockers row 6). Task 19 asserts subset.
_DISPATCH: dict[IntentCategory, SelectedTarget] = {
    IntentCategory.RESEARCH_MEETING_PREP: SelectedTarget(
        kind="pipeline", name="m8.research_pipeline_1"
    ),
    IntentCategory.RESEARCH_PORTFOLIO_REVIEW: SelectedTarget(
        kind="pipeline", name="m8.research_pipeline_2"
    ),
    IntentCategory.RESEARCH_MARKET_QUERY: SelectedTarget(
        kind="pipeline", name="m8.research_single_tool"
    ),
    IntentCategory.RESEARCH_HOUSEHOLD_SUMMARY: SelectedTarget(
        kind="pipeline", name="m8.research_pipeline_3"
    ),
    IntentCategory.CLIENT_DATA_LOOKUP: SelectedTarget(
        kind="tool", name="sfdc.fetch_client"
    ),
    IntentCategory.CLIENT_GOAL_TRACKING: SelectedTarget(
        kind="tool", name="m6.composed_goal_tracking"
    ),
    IntentCategory.CLIENT_PLAN_SUMMARY: SelectedTarget(
        kind="tool", name="emoney.fetch_plan_summary"
    ),
    IntentCategory.TRADE_INQUIRY: SelectedTarget(
        kind="tool", name="orion.fetch_transactions"
    ),
    IntentCategory.COMPLIANCE_QUESTION: SelectedTarget(
        kind="escalate", name="compliance_specialist"
    ),
    IntentCategory.ESCALATE_TO_HUMAN: SelectedTarget(
        kind="escalate", name="human_specialist"
    ),
    IntentCategory.UNSUPPORTED: SelectedTarget(
        kind="escalate", name="human_specialist"
    ),
}

#: Immutable dispatch table (A12 invariant).
TAXONOMY_DISPATCH: MappingProxyType = MappingProxyType(_DISPATCH)


# -----------------------------------------------------------------------------
# Authority Scope Matrix (Fix 8) -- required scopes per intent.
# -----------------------------------------------------------------------------

_ALWAYS_ALLOWED = frozenset({
    IntentCategory.COMPLIANCE_QUESTION,
    IntentCategory.ESCALATE_TO_HUMAN,
    IntentCategory.UNSUPPORTED,
})

# Each intent -> tuple of required-scope sets. ALL scopes in any one set
# must be held for that intent to proceed. Research accepts either
# research.read OR research.execute per matrix row.
_REQUIRED_SCOPES: dict[IntentCategory, tuple[frozenset[str], ...]] = {
    IntentCategory.RESEARCH_MEETING_PREP: (
        frozenset({"research.read"}),
        frozenset({"research.execute"}),
    ),
    IntentCategory.RESEARCH_PORTFOLIO_REVIEW: (
        frozenset({"research.read"}),
        frozenset({"research.execute"}),
    ),
    IntentCategory.RESEARCH_MARKET_QUERY: (
        frozenset({"research.read"}),
        frozenset({"research.execute"}),
    ),
    IntentCategory.RESEARCH_HOUSEHOLD_SUMMARY: (
        frozenset({"research.read"}),
        frozenset({"research.execute"}),
    ),
    IntentCategory.CLIENT_DATA_LOOKUP: (frozenset({"client.read"}),),
    IntentCategory.CLIENT_GOAL_TRACKING: (
        frozenset({"client.read", "goal.read"}),
    ),
    IntentCategory.CLIENT_PLAN_SUMMARY: (frozenset({"plan.read"}),),
    IntentCategory.TRADE_INQUIRY: (frozenset({"trade.read"}),),
}


def required_scopes(intent: IntentCategory) -> tuple[frozenset[str], ...]:
    """Return tuple of acceptable required-scope sets for the intent.

    Empty tuple -> scope check bypassed (always-allowed terminals).
    """
    if intent in _ALWAYS_ALLOWED:
        return ()
    return _REQUIRED_SCOPES.get(intent, ())


# -----------------------------------------------------------------------------
# Bedrock Converse toolConfig (AC3.2, LLM Contract JSON Schema Example).
# -----------------------------------------------------------------------------


def build_tool_schema() -> dict:
    """Return the Anthropic tool_use schema for Bedrock Converse (AC3.2).

    Enum values derive from IntentCategory (AC2.1). Fix 11 guarantees
    research.household_summary is present and client.household_summary is not.
    """
    enum_values = sorted(e.value for e in IntentCategory)
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": "routing_decision",
                    "description": (
                        "Classify the user utterance into exactly one FSI "
                        "intent category with calibrated confidence and "
                        "extracted entities."
                    ),
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "required": ["intent", "confidence", "entities"],
                            "additionalProperties": False,
                            "properties": {
                                "intent": {"type": "string", "enum": enum_values},
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "entities": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                            },
                        }
                    },
                }
            }
        ],
        "toolChoice": {"tool": {"name": "routing_decision"}},
    }


# -----------------------------------------------------------------------------
# Invariants A1-A19 (Appendix A) -- asserted at import time.
# -----------------------------------------------------------------------------

_M8_PIPELINE_RE = re.compile(r"^m8\.research_(pipeline_[1-3]|single_tool)$")
_TOOL_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_RESEARCH_PREFIX = "research."
_CLIENT_PREFIX = "client."
_TRADE_PREFIX = "trade."
_COMPLIANCE_PREFIX = "compliance."


def _validate_taxonomy() -> None:
    """Assert A1-A19 at module import (fail-loud bad states).

    Raises AssertionError on violation. Called exactly once below.
    """
    # A1: 11 members.
    assert len(IntentCategory) == 11, (
        "taxonomy change requires SemVer bump"
    )

    # A2: dispatch covers every enum member.
    assert set(TAXONOMY_DISPATCH.keys()) == set(IntentCategory), (
        f"dispatch missing entries: "
        f"{set(IntentCategory) - set(TAXONOMY_DISPATCH.keys())}"
    )

    # A3: validated by SelectedTarget Literal (Pydantic).
    # A4-A6: terminal escalates.
    assert TAXONOMY_DISPATCH[IntentCategory.COMPLIANCE_QUESTION].kind == "escalate"
    assert (
        TAXONOMY_DISPATCH[IntentCategory.COMPLIANCE_QUESTION].name
        == "compliance_specialist"
    ), "Steering Rule 14 violation"
    assert TAXONOMY_DISPATCH[IntentCategory.ESCALATE_TO_HUMAN].kind == "escalate"
    assert TAXONOMY_DISPATCH[IntentCategory.ESCALATE_TO_HUMAN].name == "human_specialist"
    assert TAXONOMY_DISPATCH[IntentCategory.UNSUPPORTED].kind == "escalate"
    assert TAXONOMY_DISPATCH[IntentCategory.UNSUPPORTED].name == "human_specialist"

    # Count buckets (A9-A11).
    pipeline_targets = [
        t for t in TAXONOMY_DISPATCH.values() if t.kind == "pipeline"
    ]
    tool_targets = [t for t in TAXONOMY_DISPATCH.values() if t.kind == "tool"]
    escalate_targets = [
        t for t in TAXONOMY_DISPATCH.values() if t.kind == "escalate"
    ]

    # A7: every pipeline matches M8 name pattern.
    for t in pipeline_targets:
        assert _M8_PIPELINE_RE.match(t.name), (
            f"pipeline name {t.name!r} does not match M8 naming contract"
        )

    # A8: tool names have namespace.
    for t in tool_targets:
        assert _TOOL_NAMESPACE_RE.match(t.name), (
            f"tool name {t.name!r} missing namespace separator"
        )

    # A9: 4 pipeline targets.
    assert len(pipeline_targets) == 4, (
        f"Phase 2 expects exactly 4 pipeline targets, got {len(pipeline_targets)}"
    )
    # A10: 4 tool targets.
    assert len(tool_targets) == 4, (
        f"Phase 2 expects exactly 4 tool targets, got {len(tool_targets)}"
    )
    # A11: 3 escalate targets.
    assert len(escalate_targets) == 3, (
        f"Phase 2 expects exactly 3 escalate targets, got {len(escalate_targets)}"
    )

    # A12: immutability.
    assert isinstance(TAXONOMY_DISPATCH, MappingProxyType)

    # A13: alphabetical enum ordering.
    values = [e.value for e in IntentCategory]
    assert values == sorted(values), (
        "enum must be alphabetically ordered for tie-break determinism"
    )

    # A15: VALID_REASON_CODES frozen + 13 codes.
    from m9_intent_router.errors import VALID_REASON_CODES
    assert isinstance(VALID_REASON_CODES, frozenset)
    assert len(VALID_REASON_CODES) == 13, (
        f"VALID_REASON_CODES count mismatch: {len(VALID_REASON_CODES)} != 13"
    )

    # A16: no MNPI category name leaks into reason_code vocabulary.
    for code in VALID_REASON_CODES:
        for banned in ("ssn", "routing", "bank", "account_number"):
            assert banned not in code, (
                f"MNPI category must not leak into reason_code: {code!r}"
            )

    # A18: no kind has an empty name (Pydantic min_length=1 enforces).
    for t in TAXONOMY_DISPATCH.values():
        assert len(t.name) > 0

    # A19 (Fix 11): prefix-kind consistency.
    for intent, target in TAXONOMY_DISPATCH.items():
        value = intent.value
        if target.kind == "pipeline":
            assert value.startswith(_RESEARCH_PREFIX), (
                f"prefix-kind invariant violation: {value!r} cannot route to kind=pipeline"
            )
        elif target.kind == "tool":
            assert value.startswith(_CLIENT_PREFIX) or value.startswith(
                _TRADE_PREFIX
            ), (
                f"prefix-kind invariant violation: {value!r} cannot route to kind=tool"
            )
        elif target.kind == "escalate":
            allowed = (
                value.startswith(_COMPLIANCE_PREFIX)
                or value == "escalate_to_human"
                or value == "unsupported"
            )
            assert allowed, (
                f"prefix-kind invariant violation: {value!r} cannot route to kind=escalate"
            )


# Run invariants at import time.
_validate_taxonomy()

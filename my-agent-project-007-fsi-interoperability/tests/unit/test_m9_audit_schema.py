"""
M9 Task 10 -- Audit schema round-trip + meta-validation.

AC9.8 + Recommended Fix 9.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator, validate
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m9_intent_router"
    / "schemas"
    / "m9_audit_payload.schema.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_audit_schema_meta_validates():
    """Recommended Fix 9 -- schema validates against JSON Schema 2020-12."""
    schema = _schema()
    Draft202012Validator.check_schema(schema)


def test_round_trip_valid_payload(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """audit_payload() output validates against the shipped schema."""
    from m9_intent_router import IntentCategory, route
    from m9_intent_router.models import LlmClassification

    utter = "prep me for meeting"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {
            utter: LlmClassification(
                intent=IntentCategory.RESEARCH_MEETING_PREP,
                confidence=0.97,
                entities={"ticker": "NVDA"},
                latency_ms=50,
                model="fake",
                provider="fake",
            )
        }
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    payload = decision.audit_payload()
    encoded = json.dumps(payload, sort_keys=True)
    assert isinstance(encoded, str)
    validate(instance=payload, schema=_schema())


def test_schema_rejects_extra_fields():
    payload = {
        "trace_id": "t",
        "utterance_sha256": "a" * 64,
        "intent": "research.meeting_prep",
        "confidence": 0.5,
        "selected_target": {"kind": "pipeline", "name": "x.y"},
        "fallback_used": False,
        "llm_latency_ms": 10,
        "llm_model": "m",
        "llm_provider": "p",
        "reason_code": None,
        "entities_present": [],
        "tenant_id": "t",
        "EXTRA": "nope",
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_schema())

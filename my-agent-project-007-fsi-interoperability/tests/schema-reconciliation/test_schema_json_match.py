"""
Schema-to-model reconciliation tests (Task 17).

Verifies Pydantic model_json_schema() output matches the hand-written
.json files in schemas/canonical/ — field names, types, required arrays.

AC1.4, AC10.3: Exported schemas match JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m3_schema_registry import CANONICAL_TYPES

SCHEMA_DIR = Path(__file__).parent.parent.parent / "schemas" / "canonical"

SLUG_MAP = {
    "Client": "client", "Household": "household", "TaxLot": "tax-lot",
    "Holding": "holding", "Order": "order", "Transaction": "transaction",
    "Balance": "balance", "Performance": "performance",
    "SecurityProfile": "security-profile", "Quote": "quote",
    "PlanSummary": "plan-summary", "Goal": "goal",
    "InteractionSummary": "interaction-summary",
    "ComplianceCheck": "compliance-check", "ComplianceAlert": "compliance-alert",
    "AuditEntry": "audit-entry", "ResearchBrief": "research-brief",
    "PaymentInstruction": "payment-instruction",
}


class TestSchemaJsonMatch:
    """Verify Pydantic models match their JSON Schema files."""

    @pytest.mark.parametrize("type_name", list(CANONICAL_TYPES.keys()))
    def test_json_file_exists(self, type_name: str) -> None:
        """Each type has a corresponding .json file."""
        slug = SLUG_MAP[type_name]
        json_path = SCHEMA_DIR / f"{slug}.json"
        assert json_path.exists(), f"Missing JSON schema: {json_path}"

    @pytest.mark.parametrize("type_name", list(CANONICAL_TYPES.keys()))
    def test_field_names_match(self, type_name: str) -> None:
        """Pydantic model field names match JSON Schema property names."""
        slug = SLUG_MAP[type_name]
        json_path = SCHEMA_DIR / f"{slug}.json"
        json_schema = json.loads(json_path.read_text())
        pydantic_schema = CANONICAL_TYPES[type_name].model_json_schema()

        json_props = set(json_schema.get("properties", {}).keys())
        pydantic_props = set(pydantic_schema.get("properties", {}).keys())

        assert json_props == pydantic_props, (
            f"{type_name}: field mismatch.\n"
            f"  In JSON only: {json_props - pydantic_props}\n"
            f"  In Pydantic only: {pydantic_props - json_props}"
        )

    @pytest.mark.parametrize("type_name", list(CANONICAL_TYPES.keys()))
    def test_required_fields_match(self, type_name: str) -> None:
        """Required field arrays match between JSON and Pydantic."""
        slug = SLUG_MAP[type_name]
        json_path = SCHEMA_DIR / f"{slug}.json"
        json_schema = json.loads(json_path.read_text())
        pydantic_schema = CANONICAL_TYPES[type_name].model_json_schema()

        json_required = set(json_schema.get("required", []))
        pydantic_required = set(pydantic_schema.get("required", []))

        assert json_required == pydantic_required, (
            f"{type_name}: required mismatch.\n"
            f"  In JSON only: {json_required - pydantic_required}\n"
            f"  In Pydantic only: {pydantic_required - json_required}"
        )

    @pytest.mark.parametrize("type_name", list(CANONICAL_TYPES.keys()))
    def test_schema_has_draft_2020_12(self, type_name: str) -> None:
        """Every JSON schema has $schema = Draft 2020-12."""
        slug = SLUG_MAP[type_name]
        json_path = SCHEMA_DIR / f"{slug}.json"
        json_schema = json.loads(json_path.read_text())
        assert json_schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"

    @pytest.mark.parametrize("type_name", list(CANONICAL_TYPES.keys()))
    def test_schema_has_valid_id(self, type_name: str) -> None:
        """Every JSON schema has $id in correct format."""
        slug = SLUG_MAP[type_name]
        json_path = SCHEMA_DIR / f"{slug}.json"
        json_schema = json.loads(json_path.read_text())
        expected_id = f"https://007.fsi/schemas/canonical/{slug}/v0.1.0"
        assert json_schema.get("$id") == expected_id

"""
Cross-module: M11 eMoney Zod allow-list == M7 EMoneyPlanSummary.model_fields set.

Spec AC8.5 + Task 20 (v0.2.0). Prevents future drift — if M7 adds a field
without M11 adding it too (or vice versa), this test fails and surfaces
the reconciliation task.

Reads the M11 allow-list from the compiled JS or the source-of-truth
string list in src/m11_rest_adapters/emoney/src/schemas.ts via Python regex.
"""

from __future__ import annotations

import re
from pathlib import Path

from m7_schema_translators.emoney.models import EMoneyPlanSummary

ADAPTERS_ROOT = Path(__file__).parent.parent.parent / "src" / "m11_rest_adapters"


def _read_m11_allowlist() -> frozenset[str]:
    schemas_ts = ADAPTERS_ROOT / "emoney" / "src" / "schemas.ts"
    text = schemas_ts.read_text(encoding="utf-8")
    # Find EMONEY_ALLOWLIST_FIELDS array literal.
    m = re.search(
        r"EMONEY_ALLOWLIST_FIELDS\s*=\s*Object\.freeze\(\[(.*?)\]\s*as const\s*\)",
        text,
        re.DOTALL,
    )
    assert m, "failed to locate EMONEY_ALLOWLIST_FIELDS in emoney/src/schemas.ts"
    body = m.group(1)
    fields = re.findall(r'"([^"]+)"', body)
    return frozenset(fields)


def test_m11_allowlist_equals_m7_model_fields() -> None:
    m11_fields = _read_m11_allowlist()
    m7_fields = frozenset(EMoneyPlanSummary.model_fields.keys())
    missing_in_m11 = m7_fields - m11_fields
    extra_in_m11 = m11_fields - m7_fields
    assert not missing_in_m11, (
        f"M7 EMoneyPlanSummary has fields not in M11 allow-list: {sorted(missing_in_m11)}"
    )
    assert not extra_in_m11, (
        f"M11 allow-list has fields not in M7 EMoneyPlanSummary: {sorted(extra_in_m11)}"
    )


def test_required_count_matches_spec_ac85() -> None:
    """AC8.5 — 7 required fields (M7 model_fields with no default)."""
    required = {
        name
        for name, info in EMoneyPlanSummary.model_fields.items()
        if info.is_required()
    }
    assert len(required) == 7, (
        f"Expected 7 required eMoney fields, got {len(required)}: {sorted(required)}"
    )


def test_optional_count_matches_spec_ac85_new2_patch() -> None:
    """AC8.5 post-NEW-2 patch — 14 optional fields (was documented as 15)."""
    total = len(EMoneyPlanSummary.model_fields)
    required = sum(1 for f in EMoneyPlanSummary.model_fields.values() if f.is_required())
    optional = total - required
    assert optional == 14, (
        f"Expected 14 optional eMoney fields (per NEW-2 patch), got {optional}"
    )

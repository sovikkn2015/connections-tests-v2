"""
Gap 3 — Deterministic YAML manifest generator.

Produces wsp-to-rego-mapping.yaml that CI consumes. Same inputs →
byte-identical output → identical SHA-256 digest.

See .kiro/specs/gap3-wsp-to-yaml.md R3.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import yaml

from compliance.gap3_wsp_to_yaml.models import _PII_PATTERNS  # type: ignore[attr-defined]
from compliance.gap3_wsp_to_yaml.registry import MappingRegistry

_MANIFEST_SCHEMA_VERSION: str = "1.0.0"

_UPDATED_BY_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9._+\-@\s]{1,120}$")


def _reject_pii(value: str, field_name: str) -> str:
    for code, pattern in _PII_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"{field_name} contains potential PII pattern: {code}"
            )
    return value


def _iso_utc_z(dt: datetime) -> str:
    """Same Z-suffixed UTC format as Gap 2's canonical JSON."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("generated_at must be tz-aware")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mapping_dict(m: Any) -> dict[str, Any]:
    """Convert one WspMapping to a plain ordered dict for YAML dump."""
    sec = m.wsp_section
    rules_out: list[dict[str, Any]] = []
    for a in m.rules:
        rules_out.append(
            {
                "opa_bundle": a.opa_bundle,
                "rego_file": a.rego_file,
                "rego_rule": a.rego_rule,
                "rule_applied": a.rule_applied,
            }
        )
    return {
        "escalation_path": list(sec.escalation_path),
        "frequency": sec.frequency.value,
        "last_reviewed": sec.last_reviewed.isoformat() if sec.last_reviewed else None,
        "rules": rules_out,
        "supervisory_role": sec.supervisory_role.value,
        "wsp_section": sec.section_id,
        "wsp_title": sec.title,
    }


def generate_manifest(
    registry: MappingRegistry,
    *,
    generated_at: datetime,
    last_updated_by: str,
) -> str:
    """Emit a deterministic YAML manifest.

    Raises:
        ValueError: registry has zero sections, naive generated_at,
            PII in last_updated_by, or illegal last_updated_by shape.
    """
    if not registry.sections:
        raise ValueError("registry has zero sections")

    if not isinstance(last_updated_by, str) or not last_updated_by:
        raise ValueError("last_updated_by must be non-empty string")
    if len(last_updated_by) > 120:
        raise ValueError("last_updated_by exceeds 120 chars")
    if not _UPDATED_BY_RE.match(last_updated_by):
        raise ValueError(
            "last_updated_by contains disallowed characters"
        )
    _reject_pii(last_updated_by, "last_updated_by")

    ts = _iso_utc_z(generated_at)  # raises on naive

    # wsp_document_id = the common wsp_id. Take the first section's
    # wsp_id (invariant: a registry is built from one ingest call, so
    # all sections share wsp_id). If the invariant fails, fail-closed.
    wsp_ids = {s.wsp_id for s in registry.sections}
    if len(wsp_ids) != 1:
        raise ValueError(
            f"registry spans multiple wsp_ids: {sorted(wsp_ids)!r}"
        )
    wsp_document_id = next(iter(wsp_ids))

    mappings_out = [_mapping_dict(m) for m in registry.mappings]

    doc: dict[str, Any] = {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "generated_at": ts,
        "last_updated_by": last_updated_by,
        "wsp_document_id": wsp_document_id,
        "mappings": mappings_out,
    }

    return yaml.safe_dump(
        doc,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def sha256_digest(manifest_text: str) -> str:
    """SHA-256 hex of the UTF-8 encoded manifest. Determinism anchor."""
    if not isinstance(manifest_text, str):
        raise TypeError("manifest_text must be str")
    return hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

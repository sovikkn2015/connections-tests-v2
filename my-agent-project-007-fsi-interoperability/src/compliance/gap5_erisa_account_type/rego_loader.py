"""
Gap 5 — Rego bundle manifest loader + wsp_section validator.

The Python engine is the execution-of-record for Phase 2-3; the Rego
files mirror the truth tables so that a future real-OPA integration
is a wiring change, not a logic change.

This loader:
  - reads `opa-bundles/account-type/manifest.json`,
  - confirms every referenced `.rego` rule carries a wsp_section
    annotation in the allowed Gap 5 vocabulary (R6.2),
  - refuses to return a manifest otherwise (fail-closed).

See .kiro/specs/gap5-erisa-account-type.md R6.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from compliance.gap5_erisa_account_type._types import (
    ALLOWED_WSP_SECTIONS,
    RegoManifestError,
)

# Very conservative wsp_section extraction regex — matches
# `# wsp_section: "<value>"` lines inside the METADATA block.
_WSP_LINE_RE: re.Pattern[str] = re.compile(
    r"^\s*#\s*wsp_section\s*:\s*\"([^\"]+)\"\s*$", re.MULTILINE
)


def _extract_wsp_sections(rego_path: Path) -> list[str]:
    text = rego_path.read_text(encoding="utf-8")
    return _WSP_LINE_RE.findall(text)


def load_manifest(bundle_root: Path) -> dict[str, Any]:
    """Load and validate the account-type bundle manifest.

    Returns the parsed manifest dict when all invariants hold.
    Raises `RegoManifestError` on any violation.
    """
    bundle_root = Path(bundle_root)
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.exists():
        raise RegoManifestError(
            f"manifest.json not found under {bundle_root}"
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegoManifestError(f"malformed manifest.json: {exc}") from exc

    rules = manifest.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RegoManifestError(
            "manifest.json must contain non-empty 'rules' array"
        )

    for entry in rules:
        if not isinstance(entry, dict):
            raise RegoManifestError("each rules[] entry must be an object")
        file_rel = entry.get("file")
        expected_wsp = entry.get("wsp_section")
        if not isinstance(file_rel, str) or not isinstance(expected_wsp, str):
            raise RegoManifestError(
                "each rule entry must have string 'file' and 'wsp_section'"
            )
        if expected_wsp not in ALLOWED_WSP_SECTIONS:
            raise RegoManifestError(
                f"wsp_section '{expected_wsp}' not in allowed "
                f"vocabulary (R6.2)"
            )
        rego_path = bundle_root / file_rel
        if not rego_path.exists():
            raise RegoManifestError(
                f"rego file listed in manifest does not exist: {rego_path}"
            )
        found = _extract_wsp_sections(rego_path)
        if not found:
            raise RegoManifestError(
                f"rego file {rego_path} has no wsp_section annotation"
            )
        # Every annotation in the file must itself be in the allowed vocab.
        for tok in found:
            if tok not in ALLOWED_WSP_SECTIONS:
                raise RegoManifestError(
                    f"rego file {rego_path} has unknown "
                    f"wsp_section '{tok}'"
                )
        # And the manifest-declared section must appear somewhere in the file.
        if expected_wsp not in found:
            raise RegoManifestError(
                f"rego file {rego_path} does not declare "
                f"wsp_section '{expected_wsp}'"
            )

    return manifest

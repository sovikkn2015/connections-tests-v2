"""
Gap 7 — Rego bundle manifest loader + wsp_section validator.

Same contract as Gap 5's loader (parity by design): every rule under
`opa-bundles/jurisdiction/**` must carry a wsp_section annotation in
the allowed Gap 7 vocabulary (R7.2).

See .kiro/specs/gap7-cross-border.md §R7.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from compliance.gap7_cross_border._types import (
    ALLOWED_WSP_SECTIONS,
    RegoManifestError,
)

_WSP_LINE_RE: re.Pattern[str] = re.compile(
    r"^\s*#\s*wsp_section\s*:\s*\"([^\"]+)\"\s*$", re.MULTILINE
)


def _extract_wsp_sections(rego_path: Path) -> list[str]:
    return _WSP_LINE_RE.findall(rego_path.read_text(encoding="utf-8"))


def load_manifest(bundle_root: Path) -> dict[str, Any]:
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
                f"vocabulary (R7.2)"
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
        for tok in found:
            if tok not in ALLOWED_WSP_SECTIONS:
                raise RegoManifestError(
                    f"rego file {rego_path} has unknown "
                    f"wsp_section '{tok}'"
                )
        if expected_wsp not in found:
            raise RegoManifestError(
                f"rego file {rego_path} does not declare "
                f"wsp_section '{expected_wsp}'"
            )

    return manifest

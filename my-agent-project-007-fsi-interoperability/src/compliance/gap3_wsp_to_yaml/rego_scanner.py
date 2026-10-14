"""
Gap 3 — Rego file scanner.

Lightweight `.rego` scanner that extracts `wsp_section` metadata
annotations. CI uses this to fail the build when any Rego rule lacks
an annotation (steering rule 19).

See .kiro/specs/gap3-wsp-to-yaml.md R8 + §2.4.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Regex: matches a `wsp_section: "WSP-XYZ-1.2"` line inside a
# Rego METADATA block. Conservative — requires double quotes and
# a valid WSP identifier.
_WSP_IN_REGO: re.Pattern[str] = re.compile(
    r"^\s*#\s*(?:custom:\s*)?wsp_section\s*:\s*\"(WSP-[A-Z]+-\d+(?:\.\d+)?)\"\s*$",
    re.MULTILINE,
)

# Regex: matches the `wsp_section:` value line inside a `custom:`
# sub-block where the `wsp_section` key is indented under `custom:`.
# The two variants differ in leading `#` position; combine both.
_WSP_IN_REGO_CUSTOM: re.Pattern[str] = re.compile(
    r"^\s*#\s+wsp_section\s*:\s*\"(WSP-[A-Z]+-\d+(?:\.\d+)?)\"\s*$",
    re.MULTILINE,
)

_PACKAGE_LINE: re.Pattern[str] = re.compile(
    r"^\s*package\s+([a-zA-Z0-9_.]+)\s*$",
    re.MULTILINE,
)


class RegoRuleAnchor(BaseModel):
    """Minimal metadata extracted from a .rego file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rego_file: str = Field(min_length=1, max_length=400)
    package: Optional[str] = None
    wsp_sections: tuple[str, ...] = ()


def scan_rego_file(path: str | Path) -> RegoRuleAnchor:
    """Scan a single .rego file for wsp_section annotations.

    Returns a RegoRuleAnchor with whatever was found. Empty
    wsp_sections tuple means no annotation — the coverage reporter
    treats that as an orphan.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"rego file not found: {path!r}")
    text = p.read_text(encoding="utf-8")

    pkg_match = _PACKAGE_LINE.search(text)
    package = pkg_match.group(1) if pkg_match else None

    # Union of both regex variants. Deduplicated, order-preserving.
    found: list[str] = []
    seen: set[str] = set()
    for pattern in (_WSP_IN_REGO_CUSTOM, _WSP_IN_REGO):
        for m in pattern.finditer(text):
            val = m.group(1)
            if val not in seen:
                seen.add(val)
                found.append(val)

    return RegoRuleAnchor(
        rego_file=str(p),
        package=package,
        wsp_sections=tuple(found),
    )


def scan_rego_directory(directory: str | Path) -> tuple[RegoRuleAnchor, ...]:
    """Scan every .rego file under `directory` recursively.

    Results are deterministically ordered by file path (sorted ASC).
    """
    d = Path(directory)
    if not d.is_dir():
        raise NotADirectoryError(f"rego directory not found: {directory!r}")
    rego_files = sorted(str(p) for p in d.rglob("*.rego"))
    return tuple(scan_rego_file(p) for p in rego_files)

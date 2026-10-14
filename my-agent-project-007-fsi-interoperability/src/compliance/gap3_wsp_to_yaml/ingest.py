"""
Gap 3 — WSP document ingest.

Reads a YAML document describing WSP sections and returns a list of
frozen WspSection Pydantic models. Filesystem access is behind a
FileReader Protocol so tests never touch disk.

See .kiro/specs/gap3-wsp-to-yaml.md R1 + R5.3.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml
from pydantic import ValidationError

from compliance.gap3_wsp_to_yaml.models import (
    SupervisoryFrequency,
    SupervisoryRole,
    WspSection,
)


# =============================================================================
# FileReader Protocol (spec R5.3)
# =============================================================================


class WspIngestError(ValueError):
    """Raised when WSP YAML ingest fails. Single frozen reason set so
    the CLI can map to stable exit codes."""


@runtime_checkable
class FileReader(Protocol):
    """Read a file's text content. Tests override with in-memory."""

    def read_text(self, path: str) -> str: ...


class LocalFileReader:
    """Production FileReader backed by pathlib."""

    def read_text(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            raise WspIngestError(f"wsp file not found: {path!r}")
        if not p.is_file():
            raise WspIngestError(f"wsp path is not a file: {path!r}")
        try:
            return p.read_text(encoding="utf-8")
        except OSError as exc:
            raise WspIngestError(
                f"wsp read failed ({exc.__class__.__name__})"
            ) from None


class InMemoryFileReader:
    """Test FileReader backed by a dict[str, str]."""

    def __init__(self, files: dict[str, str]) -> None:
        self._files = dict(files)

    def read_text(self, path: str) -> str:
        if path not in self._files:
            raise WspIngestError(f"wsp file not found: {path!r}")
        return self._files[path]


# =============================================================================
# ingest_wsp_yaml (spec R1)
# =============================================================================


def _coerce_section(raw: Any, index: int) -> WspSection:
    """Convert a raw dict to WspSection with precise error surface."""
    if not isinstance(raw, dict):
        raise WspIngestError(
            f"wsp section at index {index} must be a mapping"
        )
    data: dict[str, Any] = dict(raw)

    # String enum coercion: YAML may yield plain strings for
    # supervisory_role / frequency — Pydantic will accept enum values,
    # but we do one explicit coercion to give a readable error.
    role = data.get("supervisory_role")
    if isinstance(role, str):
        try:
            data["supervisory_role"] = SupervisoryRole(role)
        except ValueError:
            raise WspIngestError(
                f"section at index {index}: invalid supervisory_role "
                f"{role!r}"
            ) from None

    freq = data.get("frequency")
    if isinstance(freq, str):
        try:
            data["frequency"] = SupervisoryFrequency(freq)
        except ValueError:
            raise WspIngestError(
                f"section at index {index}: invalid frequency {freq!r}"
            ) from None

    # escalation_path: YAML lists become list; Pydantic will tuple-ify.
    ep = data.get("escalation_path")
    if isinstance(ep, list):
        data["escalation_path"] = tuple(ep)

    # last_reviewed: YAML native date OK; strings coerced by Pydantic.
    lr = data.get("last_reviewed")
    if lr is None:
        pass  # allowed
    elif isinstance(lr, date):
        pass  # native
    elif isinstance(lr, str):
        pass  # Pydantic coerces ISO 8601
    else:
        raise WspIngestError(
            f"section at index {index}: last_reviewed must be date or "
            f"ISO-8601 string"
        )

    try:
        return WspSection(**data)
    except ValidationError as exc:
        # Flatten to a single WspIngestError preserving Pydantic's
        # structured message but NOT the full traceback chain.
        raise WspIngestError(
            f"section at index {index} failed validation: {exc.errors()[0]}"
        ) from None


def ingest_wsp_yaml(reader: FileReader, path: str) -> list[WspSection]:
    """Parse a WSP YAML document → list[WspSection].

    YAML shape:
        wsp_id: "WSP-ACME-2026"
        sections:
          - section_id: "WSP-TRD-3.1"
            title: "Restricted List Management"
            body: "..."
            supervisory_role: "compliance_officer"
            frequency: "real_time"
            escalation_path: ["compliance_officer", "chief_compliance_officer"]
            last_reviewed: "2026-07-01"

    Errors are normalized to WspIngestError. The CLI maps this to a
    single frozen exit reason.
    """
    if not isinstance(reader, FileReader):
        raise WspIngestError("reader does not implement FileReader")

    text = reader.read_text(path)
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WspIngestError(
            f"wsp yaml parse failed ({exc.__class__.__name__})"
        ) from None

    if not isinstance(doc, dict):
        raise WspIngestError("wsp document must be a mapping at top level")

    wsp_id = doc.get("wsp_id")
    if not isinstance(wsp_id, str) or not wsp_id:
        raise WspIngestError("wsp document missing wsp_id")

    raw_sections = doc.get("sections")
    if not isinstance(raw_sections, list):
        raise WspIngestError("wsp document sections must be a list")

    out: list[WspSection] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(raw_sections):
        if isinstance(raw, dict):
            # Inject wsp_id if missing so authors can avoid repetition.
            raw = dict(raw)
            raw.setdefault("wsp_id", wsp_id)
        sec = _coerce_section(raw, idx)
        if sec.section_id in seen_ids:
            raise WspIngestError(
                f"duplicate section_id {sec.section_id!r}"
            )
        seen_ids.add(sec.section_id)
        out.append(sec)
    return out

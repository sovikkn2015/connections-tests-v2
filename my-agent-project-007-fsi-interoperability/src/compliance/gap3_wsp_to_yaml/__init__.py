"""
Gap 3 — WSP-to-YAML Mapping — Public API.

Parent module: M2 (Authority Policy).

Build-time tooling that bridges a firm's Written Supervisory
Procedures (WSP) document to the OPA/Rego policy bundles that
implement them. Produces a deterministic YAML manifest and a
coverage report that CI uses to block merges when WSP sections
have no Rego anchor OR Rego rules have no WSP anchor.

NO runtime traffic. NO LLM calls. Pure deterministic analyzer.

Usage:
    from compliance.gap3_wsp_to_yaml import (
        WspSection, MappingRegistry, build_coverage_report,
        generate_manifest, LocalFileReader,
    )

    sections = ingest_wsp_yaml(LocalFileReader(), "wsp.yaml")
    registry = MappingRegistry.from_m2(AuthorityPolicy(), sections)
    manifest = generate_manifest(
        registry,
        generated_at=datetime.now(timezone.utc),
        last_updated_by="compliance@firm.com",
    )
    report = build_coverage_report(registry)
    assert report.exit_code == 0, f"CI gap: {report}"

See `.kiro/specs/gap3-wsp-to-yaml.md` for the full contract.
"""

from __future__ import annotations

from compliance.gap3_wsp_to_yaml.models import (
    SECTION_SCHEMA_VERSION,
    WSP_SECTION_RE,
    CoverageReport,
    RuleAnchor,
    SupervisoryFrequency,
    SupervisoryRole,
    WspMapping,
    WspSection,
)
from compliance.gap3_wsp_to_yaml.ingest import (
    FileReader,
    InMemoryFileReader,
    LocalFileReader,
    WspIngestError,
    ingest_wsp_yaml,
)
from compliance.gap3_wsp_to_yaml.registry import MappingRegistry
from compliance.gap3_wsp_to_yaml.yaml_generator import (
    generate_manifest,
    sha256_digest,
)
from compliance.gap3_wsp_to_yaml.coverage import build_coverage_report
from compliance.gap3_wsp_to_yaml.rego_scanner import (
    RegoRuleAnchor,
    scan_rego_directory,
    scan_rego_file,
)

__all__ = [
    # Constants
    "SECTION_SCHEMA_VERSION",
    "WSP_SECTION_RE",
    # Enums
    "SupervisoryRole",
    "SupervisoryFrequency",
    # Models
    "WspSection",
    "RuleAnchor",
    "WspMapping",
    "CoverageReport",
    "RegoRuleAnchor",
    # Ingest
    "FileReader",
    "LocalFileReader",
    "InMemoryFileReader",
    "WspIngestError",
    "ingest_wsp_yaml",
    # Registry + generator + coverage + rego scanner
    "MappingRegistry",
    "generate_manifest",
    "sha256_digest",
    "build_coverage_report",
    "scan_rego_file",
    "scan_rego_directory",
]

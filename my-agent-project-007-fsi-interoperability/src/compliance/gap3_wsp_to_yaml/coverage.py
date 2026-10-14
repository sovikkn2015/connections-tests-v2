"""
Gap 3 — Coverage reporter.

Computes CI-blocking exit code from a MappingRegistry. Zero sections
= CI misconfig (exit 2). strict=True promotes any orphan to exit 2.

See .kiro/specs/gap3-wsp-to-yaml.md R4.
"""

from __future__ import annotations

from compliance.gap3_wsp_to_yaml.models import CoverageReport
from compliance.gap3_wsp_to_yaml.registry import MappingRegistry


def build_coverage_report(
    registry: MappingRegistry,
    *,
    strict: bool = False,
) -> CoverageReport:
    """Build a CoverageReport from a MappingRegistry.

    Exit code ladder (R4.2):
        0 — no unmapped sections, no orphan rules, non-empty registry.
        1 — any unmapped section OR orphan rule.
        2 — strict=True AND orphan rules exist; OR registry is empty
            (CI misconfig — R4.4).

    coverage_pct and orphan_pct are banker's-rounded to 3 decimals
    (R4.3). On empty registry, both are 0.000.
    """
    if not isinstance(registry, MappingRegistry):
        raise TypeError("registry must be MappingRegistry")

    total_sections = len(registry.sections)
    total_rules = len(registry.all_rule_applieds)

    unmapped = registry.unmapped_section_ids()
    orphans = registry.orphan_rule_applieds

    mapped = total_sections - len(unmapped)

    # Empty registry is a CI-blocking misconfig (R4.4).
    if total_sections == 0:
        return CoverageReport(
            total_wsp_sections=0,
            total_rules=total_rules,
            mapped_sections=0,
            unmapped_sections=(),
            orphan_rules=tuple(sorted(orphans)),
            coverage_pct=0.000,
            orphan_pct=_pct(len(orphans), total_rules),
            exit_code=2,
        )

    coverage_pct = _pct(mapped, total_sections)
    orphan_pct = _pct(len(orphans), total_rules)

    has_unmapped = len(unmapped) > 0
    has_orphans = len(orphans) > 0
    if strict and has_orphans:
        exit_code = 2
    elif has_unmapped or has_orphans:
        exit_code = 1
    else:
        exit_code = 0

    return CoverageReport(
        total_wsp_sections=total_sections,
        total_rules=total_rules,
        mapped_sections=mapped,
        unmapped_sections=tuple(sorted(unmapped)),
        orphan_rules=tuple(sorted(orphans)),
        coverage_pct=coverage_pct,
        orphan_pct=orphan_pct,
        exit_code=exit_code,
    )


def _pct(numerator: int, denominator: int) -> float:
    """Banker's-rounded percentage to 3 decimal places."""
    if denominator <= 0:
        return 0.000
    raw = (numerator / denominator) * 100.0
    return round(raw, 3)

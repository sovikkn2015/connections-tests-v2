"""
Gap 3 — MappingRegistry.

Bidirectional cross-reference between WSP sections (by section_id) and
OPA rule identifiers (by rule_applied). Built from M2's rule_table()
joined to an ingested list[WspSection].

See .kiro/specs/gap3-wsp-to-yaml.md R2.3-R2.4 + §2.3.
"""

from __future__ import annotations

from typing import Any, Sequence

from m2_m4_policy_engine import AuthorityPolicy

from compliance.gap3_wsp_to_yaml.models import (
    RuleAnchor,
    WspMapping,
    WspSection,
)


def _opa_bundle_from(rule_applied: str) -> str:
    """Derive OPA bundle name from rule_applied path.

    Example: 'authority/advisor/restricted_list.v1' -> 'authority'.
    """
    return rule_applied.split("/", 1)[0]


def _rego_file_from(rule_applied: str) -> str:
    """Derive rego file path from rule_applied.

    'authority/advisor/restricted_list.v1' -> 'authority/restricted_list.rego'

    Strategy: strip the middle segment (role scope), strip the `.vN`
    suffix, append `.rego`. This matches opa-bundles README §Phase 2
    migration.
    """
    # rule_applied shape: {bundle}/{scope}/{name}.v{N}
    parts = rule_applied.split("/")
    if len(parts) != 3:
        raise ValueError(
            f"unexpected rule_applied shape: {rule_applied!r}"
        )
    bundle = parts[0]
    name_with_version = parts[2]
    name = name_with_version.split(".", 1)[0]
    return f"{bundle}/{name}.rego"


def _rego_rule_from(rule_applied: str) -> str:
    """Derive the Rego rule symbol from rule_applied.

    'authority/advisor/restricted_list.v1' -> 'restricted_list'
    """
    parts = rule_applied.split("/")
    if len(parts) != 3:
        raise ValueError(
            f"unexpected rule_applied shape: {rule_applied!r}"
        )
    name_with_version = parts[2]
    return name_with_version.split(".", 1)[0]


def _make_anchor(rule_applied: str) -> RuleAnchor:
    return RuleAnchor(
        rule_applied=rule_applied,
        opa_bundle=_opa_bundle_from(rule_applied),
        rego_file=_rego_file_from(rule_applied),
        rego_rule=_rego_rule_from(rule_applied),
    )


class MappingRegistry:
    """Bidirectional cross-reference between WspSection and RuleAnchor.

    Build via `MappingRegistry.from_m2(authority, sections)` (the
    canonical path) OR via `MappingRegistry.build(sections, rules)`
    where `rules` is any iterable of dicts with `rule_applied` and
    `wsp_section` keys (used for testing without the full M2 engine).
    """

    def __init__(
        self,
        *,
        sections: Sequence[WspSection],
        mappings: Sequence[WspMapping],
        all_rule_applieds: Sequence[str],
        orphan_rule_applieds: Sequence[str],
    ) -> None:
        self._sections: tuple[WspSection, ...] = tuple(sections)
        self._mappings: tuple[WspMapping, ...] = tuple(mappings)
        self._all_rule_applieds: tuple[str, ...] = tuple(all_rule_applieds)
        self._orphan_rule_applieds: tuple[str, ...] = tuple(
            orphan_rule_applieds
        )

    # ---------------------------------------------------------------------
    # Constructors
    # ---------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        sections: Sequence[WspSection],
        rules: Sequence[dict[str, Any]],
    ) -> "MappingRegistry":
        """Build a registry from explicit rule rows.

        Each ``rules`` row must have at least ``rule_applied`` and
        ``wsp_section`` keys. This is the testable seam — ``from_m2``
        is a thin wrapper around this.
        """
        sections_by_id: dict[str, WspSection] = {}
        for sec in sections:
            if sec.section_id in sections_by_id:
                raise ValueError(
                    f"duplicate section_id in sections: {sec.section_id!r}"
                )
            sections_by_id[sec.section_id] = sec

        forward: dict[str, list[RuleAnchor]] = {
            sid: [] for sid in sections_by_id
        }
        all_rules: list[str] = []
        orphans: list[str] = []

        seen_rules: set[str] = set()
        for row in rules:
            rule_applied = row.get("rule_applied")
            wsp = row.get("wsp_section")
            if not isinstance(rule_applied, str) or not rule_applied:
                raise ValueError(
                    f"rule row missing rule_applied: {row!r}"
                )
            if not isinstance(wsp, str) or not wsp:
                raise ValueError(
                    f"rule row missing wsp_section: {row!r}"
                )
            if rule_applied in seen_rules:
                # Duplicate rule_applied entries collapse; the first
                # wsp_section anchor wins for forward mapping, but the
                # rule is still catalogued once.
                continue
            seen_rules.add(rule_applied)
            all_rules.append(rule_applied)

            if wsp in sections_by_id:
                anchor = _make_anchor(rule_applied)
                forward[wsp].append(anchor)
            else:
                orphans.append(rule_applied)

        # Build WspMapping tuple, sorted by section_id ASCII ascending
        # with deterministic rule ordering.
        mappings: list[WspMapping] = []
        for sid in sorted(forward.keys()):
            anchors = sorted(forward[sid], key=lambda a: a.rule_applied)
            mappings.append(
                WspMapping(
                    wsp_section=sections_by_id[sid],
                    rules=tuple(anchors),
                )
            )

        return cls(
            sections=tuple(sections_by_id[sid] for sid in sorted(sections_by_id)),
            mappings=tuple(mappings),
            all_rule_applieds=tuple(sorted(all_rules)),
            orphan_rule_applieds=tuple(sorted(orphans)),
        )

    @classmethod
    def from_m2(
        cls,
        authority: AuthorityPolicy,
        sections: Sequence[WspSection],
    ) -> "MappingRegistry":
        """Build a registry from the M2 AuthorityPolicy rule inventory.

        Reads ``authority.rule_table()`` (READ-ONLY — no evaluation
        path is touched).
        """
        if not isinstance(authority, AuthorityPolicy):
            raise TypeError("authority must be AuthorityPolicy")
        rule_rows = authority.rule_table()
        return cls.build(sections=sections, rules=rule_rows)

    # ---------------------------------------------------------------------
    # Accessors
    # ---------------------------------------------------------------------

    @property
    def sections(self) -> tuple[WspSection, ...]:
        return self._sections

    @property
    def mappings(self) -> tuple[WspMapping, ...]:
        return self._mappings

    @property
    def all_rule_applieds(self) -> tuple[str, ...]:
        return self._all_rule_applieds

    @property
    def orphan_rule_applieds(self) -> tuple[str, ...]:
        return self._orphan_rule_applieds

    def by_wsp(self, section_id: str) -> tuple[RuleAnchor, ...]:
        """Forward lookup: section_id -> anchors (empty if unmapped)."""
        for m in self._mappings:
            if m.wsp_section.section_id == section_id:
                return m.rules
        return ()

    def by_rule(self, rule_applied: str) -> tuple[str, ...]:
        """Reverse lookup: rule_applied -> section_ids (many-to-many).

        Empty tuple means orphan (rule has no WSP anchor in the
        ingested document).
        """
        out: list[str] = []
        for m in self._mappings:
            for anchor in m.rules:
                if anchor.rule_applied == rule_applied:
                    out.append(m.wsp_section.section_id)
                    break  # one section maps to this rule at most once
        return tuple(sorted(out))

    def unmapped_section_ids(self) -> tuple[str, ...]:
        """Section IDs with zero anchors (coverage gap — CI-blocking)."""
        return tuple(
            m.wsp_section.section_id
            for m in self._mappings
            if len(m.rules) == 0
        )

    def __repr__(self) -> str:
        return (
            f"MappingRegistry(sections={len(self._sections)}, "
            f"mappings={len(self._mappings)}, "
            f"rules={len(self._all_rule_applieds)}, "
            f"orphans={len(self._orphan_rule_applieds)})"
        )

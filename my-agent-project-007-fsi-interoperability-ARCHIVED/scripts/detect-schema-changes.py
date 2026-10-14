#!/usr/bin/env python3
"""
Schema Breaking-Change Detection — CI Tool

Compares current JSON schemas against a baseline (schemas/canonical/baseline/).
Detects breaking vs non-breaking changes per semver rules.

Breaking changes (exit code 1):
  - Removed required fields
  - Type changes on existing fields
  - Enum value removals

Non-breaking changes (exit code 0, reported):
  - New optional fields
  - New enum values
  - Description changes

Usage:
  python scripts/detect-schema-changes.py
"""

import json
import os
import sys
from typing import Any

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas", "canonical")
BASELINE_DIR = os.path.join(SCHEMA_DIR, "baseline")


class Change:
    """Single schema change."""

    def __init__(self, schema: str, path: str, kind: str, detail: str, breaking: bool) -> None:
        self.schema = schema
        self.path = path
        self.kind = kind
        self.detail = detail
        self.breaking = breaking

    def __str__(self) -> str:
        tag = "BREAKING" if self.breaking else "non-breaking"
        return f"  [{tag}] {self.path}: {self.kind} — {self.detail}"


def load_schema(filepath: str) -> dict | None:
    """Load a JSON schema file. Returns None if not found."""
    if not os.path.isfile(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def get_type_str(prop: dict) -> str:
    """Extract type string from a property definition."""
    t = prop.get("type", "any")
    if isinstance(t, list):
        return "|".join(sorted(t))
    return str(t)


def get_enum_values(prop: dict) -> set | None:
    """Extract enum values from a property definition."""
    enum = prop.get("enum")
    if enum is not None:
        return {str(v) for v in enum}
    return None


def compare_properties(
    schema_name: str,
    baseline_props: dict,
    current_props: dict,
    baseline_required: list,
    current_required: list,
    path_prefix: str,
    changes: list[Change],
) -> None:
    """Recursively compare properties between baseline and current."""

    baseline_keys = set(baseline_props.keys())
    current_keys = set(current_props.keys())

    # Removed fields
    for key in baseline_keys - current_keys:
        field_path = f"{path_prefix}.{key}"
        is_required = key in baseline_required
        changes.append(Change(
            schema=schema_name,
            path=field_path,
            kind="field_removed",
            detail=f"Field removed{' (was required)' if is_required else ''}",
            breaking=is_required,
        ))

    # New fields
    for key in current_keys - baseline_keys:
        field_path = f"{path_prefix}.{key}"
        is_required = key in current_required
        if is_required:
            changes.append(Change(
                schema=schema_name,
                path=field_path,
                kind="required_field_added",
                detail="New required field added (breaking for existing producers)",
                breaking=True,
            ))
        else:
            changes.append(Change(
                schema=schema_name,
                path=field_path,
                kind="optional_field_added",
                detail="New optional field added",
                breaking=False,
            ))

    # Changed fields
    for key in baseline_keys & current_keys:
        field_path = f"{path_prefix}.{key}"
        baseline_prop = baseline_props[key]
        current_prop = current_props[key]

        if not isinstance(baseline_prop, dict) or not isinstance(current_prop, dict):
            continue

        # Type changes
        baseline_type = get_type_str(baseline_prop)
        current_type = get_type_str(current_prop)
        if baseline_type != current_type:
            changes.append(Change(
                schema=schema_name,
                path=field_path,
                kind="type_changed",
                detail=f"Type changed: {baseline_type} → {current_type}",
                breaking=True,
            ))

        # Enum changes
        baseline_enum = get_enum_values(baseline_prop)
        current_enum = get_enum_values(current_prop)
        if baseline_enum is not None and current_enum is not None:
            removed_values = baseline_enum - current_enum
            added_values = current_enum - baseline_enum
            if removed_values:
                changes.append(Change(
                    schema=schema_name,
                    path=field_path,
                    kind="enum_values_removed",
                    detail=f"Enum values removed: {sorted(removed_values)}",
                    breaking=True,
                ))
            if added_values:
                changes.append(Change(
                    schema=schema_name,
                    path=field_path,
                    kind="enum_values_added",
                    detail=f"New enum values: {sorted(added_values)}",
                    breaking=False,
                ))

        # Description changes
        baseline_desc = baseline_prop.get("description", "")
        current_desc = current_prop.get("description", "")
        if baseline_desc != current_desc and baseline_desc and current_desc:
            changes.append(Change(
                schema=schema_name,
                path=field_path,
                kind="description_changed",
                detail="Description updated",
                breaking=False,
            ))

        # Required field changes
        was_required = key in baseline_required
        is_required = key in current_required
        if not was_required and is_required:
            changes.append(Change(
                schema=schema_name,
                path=field_path,
                kind="field_made_required",
                detail="Field changed from optional to required",
                breaking=True,
            ))

        # Recurse into nested properties
        baseline_nested = baseline_prop.get("properties", {})
        current_nested = current_prop.get("properties", {})
        if baseline_nested or current_nested:
            compare_properties(
                schema_name,
                baseline_nested,
                current_nested,
                baseline_prop.get("required", []),
                current_prop.get("required", []),
                field_path,
                changes,
            )


def compare_schema(schema_name: str, baseline: dict, current: dict) -> list[Change]:
    """Compare a single schema against its baseline."""
    changes: list[Change] = []

    baseline_props = baseline.get("properties", {})
    current_props = current.get("properties", {})
    baseline_required = baseline.get("required", [])
    current_required = current.get("required", [])

    # Check for removed required fields at top level
    for req in baseline_required:
        if req not in current_required:
            changes.append(Change(
                schema=schema_name,
                path=f"required.{req}",
                kind="required_field_dropped",
                detail=f"Field '{req}' removed from required list",
                breaking=True,
            ))

    # Check for new required fields at top level
    for req in current_required:
        if req not in baseline_required and req in baseline_props:
            changes.append(Change(
                schema=schema_name,
                path=f"required.{req}",
                kind="field_made_required",
                detail=f"Existing field '{req}' made required",
                breaking=True,
            ))

    compare_properties(
        schema_name,
        baseline_props,
        current_props,
        baseline_required,
        current_required,
        schema_name,
        changes,
    )

    # Version change detection
    baseline_id = baseline.get("$id", "")
    current_id = current.get("$id", "")
    if baseline_id != current_id:
        changes.append(Change(
            schema=schema_name,
            path="$id",
            kind="version_changed",
            detail=f"Schema version: {baseline_id} → {current_id}",
            breaking=False,
        ))

    return changes


def main() -> int:
    baseline_dir = os.path.abspath(BASELINE_DIR)
    schema_dir = os.path.abspath(SCHEMA_DIR)

    if not os.path.isdir(baseline_dir):
        print(f"FAIL: Baseline directory not found: {baseline_dir}")
        print("Run: cp schemas/canonical/*.json schemas/canonical/baseline/")
        return 1

    all_changes: list[Change] = []
    schemas_checked = 0
    schemas_with_changes = 0

    # Check all baseline schemas
    for filename in sorted(os.listdir(baseline_dir)):
        if not filename.endswith(".json"):
            continue

        schemas_checked += 1
        schema_name = filename.replace(".json", "")

        baseline = load_schema(os.path.join(baseline_dir, filename))
        current = load_schema(os.path.join(schema_dir, filename))

        if baseline is None:
            print(f"WARN: Baseline missing: {filename}")
            continue

        if current is None:
            all_changes.append(Change(
                schema=schema_name,
                path="/",
                kind="schema_removed",
                detail=f"Schema {filename} removed entirely",
                breaking=True,
            ))
            schemas_with_changes += 1
            continue

        changes = compare_schema(schema_name, baseline, current)
        if changes:
            schemas_with_changes += 1
            all_changes.extend(changes)

    # Check for new schemas not in baseline
    for filename in sorted(os.listdir(schema_dir)):
        if not filename.endswith(".json"):
            continue
        if not os.path.isfile(os.path.join(baseline_dir, filename)):
            all_changes.append(Change(
                schema=filename.replace(".json", ""),
                path="/",
                kind="schema_added",
                detail=f"New schema: {filename}",
                breaking=False,
            ))

    # Report
    breaking = [c for c in all_changes if c.breaking]
    non_breaking = [c for c in all_changes if not c.breaking]

    print("=" * 70)
    print("SCHEMA BREAKING-CHANGE DETECTION REPORT")
    print("=" * 70)
    print(f"Schemas checked: {schemas_checked}")
    print(f"Schemas with changes: {schemas_with_changes}")
    print(f"Breaking changes: {len(breaking)}")
    print(f"Non-breaking changes: {len(non_breaking)}")
    print()

    if breaking:
        print("─── BREAKING CHANGES ───────────────────────────────────────────")
        for c in breaking:
            print(f"  {c.schema}:")
            print(f"    {c}")
        print()

    if non_breaking:
        print("─── Non-Breaking Changes ───────────────────────────────────────")
        for c in non_breaking:
            print(f"  {c.schema}:")
            print(f"    {c}")
        print()

    if not all_changes:
        print("No schema changes detected. Baseline matches current.")
        print()

    print("=" * 70)
    if breaking:
        print(f"RESULT: FAIL — {len(breaking)} breaking change(s) detected")
        print("Action: Update baseline after review: cp schemas/canonical/*.json schemas/canonical/baseline/")
        return 1

    print("RESULT: PASS — no breaking changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

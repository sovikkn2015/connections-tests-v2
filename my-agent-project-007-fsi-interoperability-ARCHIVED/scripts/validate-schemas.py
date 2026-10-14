#!/usr/bin/env python3
"""
CI Schema Validation — ISSUE 8

Validates all 18 canonical JSON schemas in schemas/canonical/:
  1. Valid JSON parse
  2. Valid JSON Schema Draft 2020-12 ($schema present)
  3. $id format: https://007.fsi/schemas/canonical/{type}/v{MAJOR}.{MINOR}.{PATCH}
  4. All properties have "description" (Rule 3)

Exit code 0 = pass, 1 = fail.
"""

import json
import os
import re
import sys

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas", "canonical")
EXPECTED_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ID_PATTERN = re.compile(
    r"^https://007\.fsi/schemas/canonical/[a-z][a-z0-9-]+/v\d+\.\d+\.\d+$"
)

EXPECTED_SCHEMAS = [
    "audit-entry.json", "balance.json", "client.json", "compliance-alert.json",
    "compliance-check.json", "goal.json", "holding.json", "household.json",
    "interaction-summary.json", "order.json", "payment-instruction.json",
    "performance.json", "plan-summary.json", "quote.json", "research-brief.json",
    "security-profile.json", "tax-lot.json", "transaction.json",
]


def check_descriptions(props: dict, path: str, errors: list[str]) -> None:
    """Recursively check that every property has a description."""
    for name, defn in props.items():
        if not isinstance(defn, dict):
            continue
        field_path = f"{path}.{name}"
        if "description" not in defn and "$ref" not in defn:
            errors.append(f"  Missing description: {field_path}")
        if "properties" in defn:
            check_descriptions(defn["properties"], field_path, errors)


def validate_schema(filepath: str) -> list[str]:
    """Validate a single schema file. Returns list of error strings."""
    errors: list[str] = []

    try:
        with open(filepath, "r") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        return [f"  Invalid JSON: {e}"]

    dialect = schema.get("$schema")
    if dialect != EXPECTED_SCHEMA_DIALECT:
        errors.append(f"  Wrong $schema: {dialect} (expected {EXPECTED_SCHEMA_DIALECT})")

    schema_id = schema.get("$id", "")
    if not ID_PATTERN.match(schema_id):
        errors.append(f"  Invalid $id format: {schema_id}")

    props = schema.get("properties", {})
    if not props:
        errors.append("  No properties found")
    else:
        check_descriptions(props, os.path.basename(filepath), errors)

    return errors


def main() -> int:
    schema_dir = os.path.abspath(SCHEMA_DIR)
    if not os.path.isdir(schema_dir):
        print(f"FAIL: Schema directory not found: {schema_dir}")
        return 1

    total_errors = 0
    total_schemas = 0
    missing = []

    for expected in EXPECTED_SCHEMAS:
        path = os.path.join(schema_dir, expected)
        if not os.path.isfile(path):
            missing.append(expected)

    if missing:
        print(f"FAIL: Missing schemas: {', '.join(missing)}")
        total_errors += len(missing)

    for filename in sorted(os.listdir(schema_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(schema_dir, filename)
        total_schemas += 1
        errors = validate_schema(filepath)
        if errors:
            print(f"FAIL: {filename}")
            for e in errors:
                print(e)
            total_errors += len(errors)
        else:
            print(f"  OK: {filename}")

    print(f"\n{'='*60}")
    print(f"Schemas validated: {total_schemas}")
    print(f"Errors found: {total_errors}")

    if total_errors > 0:
        print("RESULT: FAIL")
        return 1

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

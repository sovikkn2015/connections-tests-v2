#!/usr/bin/env python3
"""
Validate all 18 canonical JSON Schema files in schemas/canonical/.

Checks:
  1. Valid JSON parse
  2. $schema = Draft 2020-12
  3. $id format: https://007.fsi/schemas/canonical/{type}/v{semver}
  4. Every property has a "description"
  5. Client PII fields have "x-pii": true

Exit code 0 = all pass, 1 = failures found.
Placed in scripts/ at project root for CI (pragmatic per LLMJ v2 review).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent / "schemas" / "canonical"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
ID_PATTERN = re.compile(r"^https://007\.fsi/schemas/canonical/[a-z0-9-]+/v\d+\.\d+\.\d+$")
CLIENT_PII_FIELDS = {"email", "phone", "date_of_birth", "ssn_last_four", "tax_id"}

EXPECTED_FILES = [
    "client.json", "household.json", "tax-lot.json", "holding.json",
    "order.json", "transaction.json", "balance.json", "performance.json",
    "security-profile.json", "quote.json", "plan-summary.json", "goal.json",
    "interaction-summary.json", "compliance-check.json", "compliance-alert.json",
    "audit-entry.json", "research-brief.json", "payment-instruction.json",
]


def validate_descriptions(properties: dict, path: str, errors: list[str]) -> None:
    """Check every property has a description."""
    for prop_name, prop_schema in properties.items():
        if isinstance(prop_schema, dict):
            if "description" not in prop_schema and "allOf" not in prop_schema and "$ref" not in prop_schema:
                errors.append(f"  {path}.{prop_name}: missing 'description'")


def main() -> int:
    errors: list[str] = []

    # Check all expected files exist
    for fname in EXPECTED_FILES:
        fpath = SCHEMA_DIR / fname
        if not fpath.exists():
            errors.append(f"MISSING: {fname}")

    # Validate each schema file
    for json_file in sorted(SCHEMA_DIR.glob("*.json")):
        file_errors: list[str] = []

        # 1. Valid JSON
        try:
            schema = json.loads(json_file.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{json_file.name}: invalid JSON — {e}")
            continue

        # 2. $schema
        if schema.get("$schema") != DRAFT_2020_12:
            file_errors.append(f"  $schema: expected '{DRAFT_2020_12}', got '{schema.get('$schema')}'")

        # 3. $id format
        schema_id = schema.get("$id", "")
        if not ID_PATTERN.match(schema_id):
            file_errors.append(f"  $id: '{schema_id}' does not match pattern")

        # 4. Descriptions on properties
        props = schema.get("properties", {})
        validate_descriptions(props, json_file.stem, file_errors)

        # 5. Client PII fields
        if json_file.name == "client.json":
            for pii_field in CLIENT_PII_FIELDS:
                if pii_field in props:
                    if not props[pii_field].get("x-pii"):
                        file_errors.append(f"  Client.{pii_field}: missing 'x-pii: true'")

        if file_errors:
            errors.append(f"{json_file.name}:")
            errors.extend(file_errors)

    if errors:
        print("SCHEMA VALIDATION FAILED:")
        for e in errors:
            print(e)
        return 1

    print(f"All {len(EXPECTED_FILES)} schemas validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

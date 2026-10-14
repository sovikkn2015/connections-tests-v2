"""
Vendor ID character-set validation (AC10.8).

Vendor IDs MUST match `^[a-zA-Z0-9._\\-]+$` to prevent `:`-delimiter collisions
in `f"{vendor}:{vendor_id}"` namespace key formats. Non-conformant vendor IDs
raise `TypeCoercionError(reason_code="vendor_id_invalid_chars")`.
"""

from __future__ import annotations

import re

from m7_schema_translators.errors import TypeCoercionError

_VENDOR_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._\-]+$")


def validate_vendor_id_chars(
    vendor_id: object,
    *,
    vendor: str,
    canonical_type: str,
    field_path: str,
) -> str:
    """Return the vendor_id if valid; raise `TypeCoercionError` otherwise."""
    if not isinstance(vendor_id, str) or not _VENDOR_ID_PATTERN.match(vendor_id):
        raise TypeCoercionError(
            reason_code="vendor_id_invalid_chars",
            vendor=vendor,
            canonical_type=canonical_type,
            field_path=field_path,
            details={
                "expected_type": "vendor_id matching ^[a-zA-Z0-9._\\-]+$",
                "got_type": "contains_disallowed_characters",
            },
        )
    return vendor_id

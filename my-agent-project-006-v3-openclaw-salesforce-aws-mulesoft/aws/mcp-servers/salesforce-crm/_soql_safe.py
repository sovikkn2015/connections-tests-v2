"""SOQL-injection-safe query builders.

Key discipline:
- Identifiers validated via strict regex before interpolation.
- Literal values single-quoted + escaped.
- User-supplied strings never touch a SOQL query without `escape_literal`.
"""

from __future__ import annotations

import re
from typing import Any


_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,78}[A-Za-z0-9]$|^[A-Za-z]$")
_DOTTED_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]{0,78}(?:\.[A-Za-z][A-Za-z0-9_]{0,78}){0,3}$"
)


class SoqlSafeError(ValueError):
    """Raised when an identifier or literal violates safe-build rules."""


def validate_identifier(name: str, *, allow_dotted: bool = False) -> str:
    if not isinstance(name, str):
        raise SoqlSafeError(f"Identifier must be string, got {type(name).__name__}")
    if allow_dotted:
        if not _DOTTED_RE.fullmatch(name):
            raise SoqlSafeError(f"Invalid dotted identifier: {name!r}")
    else:
        if not _IDENTIFIER_RE.fullmatch(name):
            raise SoqlSafeError(f"Invalid identifier: {name!r}")
    return name


def escape_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
        return f"'{escaped}'"
    raise SoqlSafeError(f"Unsupported literal type: {type(value).__name__}")


def build_select(
    sobject: str,
    fields: list[str],
    where: dict[str, Any] | None = None,
    limit: int | None = None,
    order_by: str | None = None,
) -> str:
    validate_identifier(sobject)
    if not fields:
        raise SoqlSafeError("At least one field required")
    for f in fields:
        validate_identifier(f, allow_dotted=True)

    clauses = [f"SELECT {', '.join(fields)} FROM {sobject}"]

    if where:
        where_parts = []
        for field, val in where.items():
            validate_identifier(field, allow_dotted=True)
            where_parts.append(f"{field} = {escape_literal(val)}")
        clauses.append("WHERE " + " AND ".join(where_parts))

    if order_by:
        tokens = order_by.strip().split()
        validate_identifier(tokens[0], allow_dotted=True)
        if len(tokens) > 1 and tokens[1].upper() not in {"ASC", "DESC"}:
            raise SoqlSafeError("order_by direction must be ASC or DESC")
        clauses.append(f"ORDER BY {order_by}")

    if limit is not None:
        if not isinstance(limit, int) or limit < 1 or limit > 2000:
            raise SoqlSafeError("limit must be 1..2000")
        clauses.append(f"LIMIT {limit}")

    return " ".join(clauses)


_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(UPDATE|DELETE|INSERT|UPSERT|MERGE|TRUNCATE|--|;)\b", re.IGNORECASE
)


def ensure_read_only(soql: str) -> str:
    if not isinstance(soql, str) or not soql.strip():
        raise SoqlSafeError("SOQL must be a non-empty string")
    if _FORBIDDEN_KEYWORDS.search(soql):
        raise SoqlSafeError("SOQL contains forbidden keyword (write/DDL)")
    if len(soql) > 20_000:
        raise SoqlSafeError("SOQL too long (max 20,000 chars)")
    return soql.strip()

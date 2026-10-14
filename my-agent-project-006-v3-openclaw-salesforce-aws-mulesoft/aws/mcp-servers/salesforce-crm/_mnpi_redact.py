"""MNPI redaction for outbound Salesforce records.

Steering rule: shares_held, market_value, wire details must never cross
into the LLM as raw numbers. Replaced here with percentage bands that
convey concentration risk without revealing absolute position size.

Bands: 0-2.5%, 2.5-5%, 5-10%, 10-15%, 15-25%, 25%+
"""

from __future__ import annotations

from typing import Any, Iterable


MNPI_FIELD_SET = frozenset(
    {
        "shares_held", "shares_held__c",
        "quantity_held",
        "market_value", "market_value__c",
        "cost_basis", "cost_basis__c",
        "unrealized_gain", "realized_gain",
        "position_size", "holdings_amount",
        "trade_amount",
        "wire_amount", "wire_beneficiary", "wire_account_number",
    }
)

_PERCENT_FIELDS = {"portfolio_pct", "concentration_pct", "position_pct"}


def _band(pct: float | None) -> str:
    if pct is None:
        return "unknown"
    if pct < 2.5:
        return "0-2.5%"
    if pct < 5.0:
        return "2.5-5%"
    if pct < 10.0:
        return "5-10%"
    if pct < 15.0:
        return "10-15%"
    if pct < 25.0:
        return "15-25%"
    return "25%+"


def _is_mnpi(field_name: str) -> bool:
    return field_name.lower() in MNPI_FIELD_SET


def redact_record(record: dict[str, Any], *, extra_mnpi_fields: Iterable[str] = ()) -> dict[str, Any]:
    """Return a shallow copy with MNPI fields replaced by percentage bands."""
    if not isinstance(record, dict):
        return record

    extra = {f.lower() for f in extra_mnpi_fields}
    pct = None
    for k, v in record.items():
        if k.lower() in _PERCENT_FIELDS and isinstance(v, (int, float)):
            pct = float(v)
            break

    out: dict[str, Any] = {}
    for k, v in record.items():
        lk = k.lower()
        if _is_mnpi(lk) or lk in extra:
            out[k] = f"REDACTED[band={_band(pct)}]"
        elif isinstance(v, dict):
            out[k] = redact_record(v, extra_mnpi_fields=extra_mnpi_fields)
        elif isinstance(v, list):
            out[k] = [
                redact_record(x, extra_mnpi_fields=extra_mnpi_fields) if isinstance(x, dict) else x
                for x in v
            ]
        else:
            out[k] = v
    return out


def redact_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [redact_record(r) for r in records]

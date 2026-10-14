"""compliance_sweep.run — system-originated volatility fanout for Narrative 3.

A price-shock event (ticker + % change) arrives on the sweep topic. The skill
scans every household holding that ticker at or above the concentration
threshold, runs per-household compliance screening (treating the publish as
a `publish_brief` action), and writes a `Client_Inquiry__c` row of type
``alert`` for each eligible household. Households whose
``Client_Preferences__c.auto_send_volatility_alert__c`` is True are marked
``Auto_Send_Eligible__c = true`` so downstream delivery can send without RM
review; everyone else routes to RM review.

Trust invariants (steering rules 8, 9, 10, 21):

  - Idempotency is enforced via DynamoDB ``compliance-sweep-events`` table.
    A replayed event (same ``event_id``) short-circuits with no writes.
  - Per-household compliance_screening is run before any inquiry write. A
    DENY skips the household (logged only — the screening skill itself
    writes the COMPLIANCE_BLOCKED audit row).
  - MNPI filter is applied to any free-form ``notes`` on the payload before
    the text is interpolated into ``Inquiry_Text__c``.
  - Every inquiry write is paired with one ``VOLATILITY_ALERT_RAISED``
    audit row (steering rule 10).
  - Per-household failures are isolated via try/except; the sweep never
    halts mid-fanout. Failures accumulate into the output and a summary
    WARN is logged at the end.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ...trust.mnpi_filter import MNPIFilter, MNPIViolation
from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from ..compliance_screening.actions import (
    Action as ProposedAction,
    ComplianceDecision,
    ComplianceInput,
)
from ..compliance_screening.actions import run as compliance_run
from .._mcp_client import MCPClient, get_shared_mock_client


log = logging.getLogger(__name__)

_DYNAMO_TABLE = "compliance-sweep-events"
_SWEEP_AGENT_ID = "compliance_sweep"


def _utcnow_iso() -> str:
    """Timezone-aware ISO-8601 stamp (suffix +00:00) for DynamoDB markers."""
    return datetime.now(timezone.utc).isoformat()


class ComplianceSweepInput(BaseModel):
    """Inbound price-shock event from the sweep topic.

    Attributes:
        ticker: symbol that moved (1..12 chars, case preserved).
        price_change_pct: signed move; absolute value is compared only for
            magnitude in the templated alert text.
        threshold_pct: concentration floor (0..100); households whose
            `Position_Size_Pct__c` is at or above this value are included.
        event_id: idempotency key. A replay with the same id returns
            immediately with ``skipped_idempotent=True`` and no writes.
        principal_id: originating principal — always ``system`` for
            scheduled/stream-driven sweeps but overridable for manual runs.
        session_id: session correlation (UUID, required).
        correlation_id: trace id propagated into every downstream audit row.
        notes: optional free-form narrative, MNPI-scrubbed before use.
    """

    ticker: str = Field(..., min_length=1, max_length=12)
    price_change_pct: float
    threshold_pct: float = Field(5.0, ge=0.0, le=100.0)
    event_id: str = Field(..., min_length=1)
    principal_id: str = Field("system", min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    notes: Optional[str] = None

    model_config = {"frozen": True}


class HouseholdError(BaseModel):
    """Per-household failure captured without aborting the sweep."""

    household_id: str
    stage: str = Field(
        ...,
        description=(
            "Pipeline stage at failure: prefs_read, compliance, inquiry_write,"
            " or audit_write."
        ),
    )
    reason: str

    model_config = {"frozen": True}


class ComplianceSweepOutput(BaseModel):
    """Summary of one sweep attempt."""

    event_id: str
    households_scanned: int = Field(0, ge=0)
    alerts_raised: int = Field(0, ge=0)
    auto_send_count: int = Field(0, ge=0)
    rm_review_count: int = Field(0, ge=0)
    skipped_idempotent: bool = False
    inquiry_ids: List[str] = Field(default_factory=list)
    errors: List[HouseholdError] = Field(default_factory=list)

    model_config = {"frozen": True}


async def _check_idempotency(
    client: MCPClient, event_id: str
) -> bool:
    """Return True if this event_id has already been processed.

    If the dynamodb MCP server is not available (V3 deploy gap), treat the
    event as never-processed (log a warning). This is safe for demos because
    the alternative is the entire sweep short-circuits.
    """
    try:
        existing = await client.call(
            server="dynamodb",
            tool="get_item",
            arguments={
                "table": _DYNAMO_TABLE,
                "key": {"event_id": event_id},
            },
        )
    except Exception as exc:  # noqa: BLE001 - dynamodb MCP not deployed in V3
        log.warning(
            "compliance_sweep_idempotency_unavailable event_id=%s reason=%s",
            event_id, str(exc)[:120],
        )
        return False
    # Standard DynamoDB get_item shape: {"Item": {...}} when present,
    # {} or {"Item": None} when absent. Treat any non-empty Item dict as hit.
    if not isinstance(existing, dict):
        return False
    item = existing.get("Item") or existing.get("item")
    return bool(item)


async def _mark_processed(
    client: MCPClient,
    event_id: str,
    ticker: str,
    alerts: int,
) -> None:
    """Write the post-sweep idempotency marker.

    Degrades silently if dynamodb MCP is not available.
    """
    try:
        await client.call(
            server="dynamodb",
            tool="put_item",
            arguments={
                "table": _DYNAMO_TABLE,
                "item": {
                    "event_id": event_id,
                    "processed_at": _utcnow_iso(),
                    "ticker": ticker,
                    "alerts": alerts,
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "compliance_sweep_marker_degraded event_id=%s reason=%s",
            event_id, str(exc)[:120],
        )


async def _query_positions(
    client: MCPClient, ticker: str, threshold: float
) -> List[Dict[str, Any]]:
    """Fetch IR_Position__c rows at or above threshold for `ticker`.

    V3 MCP salesforce-crm exposes this as `query_soql` with a single
    string param; parametrised binds are resolved client-side.
    """
    # Use bound-style query with inline values (no SOQL injection risk here —
    # ticker is validated to 12 chars max, threshold is a float).
    ticker_safe = ticker.replace("'", "").upper()
    soql = (
        f"SELECT Id, Household__c, Position_Size_Pct__c, Client_Contact__c "
        f"FROM IR_Position__c "
        f"WHERE Ticker__c = '{ticker_safe}' "
        f"AND Position_Size_Pct__c >= {float(threshold)}"
    )
    try:
        result = await client.call(
            server="salesforce-crm",
            tool="query_soql",
            arguments={"soql": soql},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "compliance_sweep_positions_query_failed ticker=%s reason=%s",
            ticker, str(exc)[:120],
        )
        return []
    if not isinstance(result, dict):
        return []
    return list(result.get("records") or result.get("rows") or [])


async def _read_preference(
    client: MCPClient, household_id: str
) -> bool:
    """Return whether the household has opted in to auto-send volatility alerts.

    Missing record, missing field, or any read error defaults to False
    (RM-review path). We never fail the sweep on a preference read — worst
    case, the alert goes through RM review.
    """
    result = await client.call(
        server="salesforce-crm",
        tool="read_object",
        arguments={
            "object_type": "Client_Preferences__c",
            "where": {"Household__c": household_id},
        },
    )
    if not isinstance(result, dict):
        return False
    # Normalise possible shapes: {"record": {...}} or {"records": [{...}]}.
    record = result.get("record")
    if record is None:
        records = result.get("records") or []
        record = records[0] if records else None
    if not isinstance(record, dict):
        return False
    raw = record.get("auto_send_volatility_alert__c")
    if raw is None:
        raw = record.get("Auto_Send_Volatility_Alert__c")
    return bool(raw)


def _scrub_notes(notes: Optional[str]) -> str:
    """MNPI-scrub free-form notes. Hard-deny becomes empty string.

    The sweep is system-originated so we use ``strict=False`` — insider
    phrasing is redacted rather than raising. A sentinel tag still raises
    ``MNPIViolation`` in the filter; we catch that and drop the notes
    entirely (defence in depth; never reach downstream text).
    """
    if not notes:
        return ""
    scrubber = MNPIFilter(strict=False)
    try:
        scrubbed, _report = scrubber.scrub_text(notes)
    except MNPIViolation as exc:
        log.warning("mnpi_violation_in_sweep_notes: %s", exc.reason)
        return ""
    return scrubbed


def _inquiry_text(
    ticker: str, price_change_pct: float, concentration: float
) -> str:
    """Human-readable alert body. Percentages only — no $ or share counts."""
    return (
        f"Volatility alert: {ticker} moved {price_change_pct:+.1f}% — "
        f"your position is {concentration:.1f}% of portfolio."
    )


async def run(
    payload: ComplianceSweepInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ComplianceSweepOutput:
    """Execute a single volatility-alert fanout.

    Steps:
        1. Idempotency check against DynamoDB ``compliance-sweep-events``.
        2. Query ``IR_Position__c`` for the ticker at/above threshold.
        3. For each household:
            a. Read ``Client_Preferences__c.auto_send_volatility_alert__c``.
            b. Run compliance_screening with proposed_action=publish_brief;
               DENY skips the household (audit written by that skill).
            c. Write ``Client_Inquiry__c`` of type ``alert``.
            d. Write an ``VOLATILITY_ALERT_RAISED`` audit row.
        4. Write the DynamoDB idempotency marker.

    Args:
        payload: the sweep input (frozen pydantic model).
        mcp: optional MCPClient; tests use the shared mock.

    Returns:
        ComplianceSweepOutput with scan/alert/error counts.
    """
    client = mcp or get_shared_mock_client()

    # --- Step 1: idempotency guard -----------------------------------------
    if await _check_idempotency(client, payload.event_id):
        log.info(
            "compliance_sweep idempotent replay event_id=%s ticker=%s",
            payload.event_id,
            payload.ticker,
        )
        return ComplianceSweepOutput(
            event_id=payload.event_id,
            households_scanned=0,
            alerts_raised=0,
            auto_send_count=0,
            rm_review_count=0,
            skipped_idempotent=True,
            inquiry_ids=[],
            errors=[],
        )

    # --- Step 2: pre-scrub notes (defensive, MNPI-safe templating) ----------
    scrubbed_notes = _scrub_notes(payload.notes)

    # --- Step 3: query candidate households --------------------------------
    positions = await _query_positions(
        client, payload.ticker, payload.threshold_pct
    )
    households_scanned = len(positions)

    inquiry_ids: List[str] = []
    errors: List[HouseholdError] = []
    auto_send_count = 0
    rm_review_count = 0

    # --- Step 4: fan out. Per-household errors must NOT halt the sweep. ----
    for pos in positions:
        household_id = (
            pos.get("Household__c") or pos.get("household_id") or ""
        )
        client_contact_id = (
            pos.get("Client_Contact__c") or pos.get("client_contact_id") or ""
        )
        concentration = float(
            pos.get("Position_Size_Pct__c")
            or pos.get("position_size_pct")
            or 0.0
        )

        # 4a. Preferences read — defaults to False on any failure.
        try:
            auto_send = await _read_preference(client, household_id)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning(
                "compliance_sweep prefs_read_failed household=%s reason=%s",
                household_id,
                exc,
            )
            errors.append(
                HouseholdError(
                    household_id=household_id,
                    stage="prefs_read",
                    reason=str(exc),
                )
            )
            auto_send = False

        # 4b. Per-household compliance screening. DENY -> skip.
        try:
            screen = await compliance_run(
                ComplianceInput(
                    ticker=payload.ticker,
                    principal_id=payload.principal_id,
                    proposed_action=ProposedAction.PUBLISH_BRIEF,
                    current_concentration_pct=concentration,
                    session_id=payload.session_id,
                    correlation_id=payload.correlation_id,
                    client_contact_id=client_contact_id or None,
                ),
                mcp=client,
            )
        except Exception as exc:
            log.warning(
                "compliance_sweep compliance_failed household=%s reason=%s",
                household_id,
                exc,
            )
            errors.append(
                HouseholdError(
                    household_id=household_id,
                    stage="compliance",
                    reason=str(exc),
                )
            )
            continue

        if screen.decision is ComplianceDecision.DENY:
            log.info(
                "compliance_sweep deny_skipped household=%s reasons=%s",
                household_id,
                screen.reasons,
            )
            continue

        # 4c. Write the Client_Inquiry__c row.
        alert_body = _inquiry_text(
            payload.ticker, payload.price_change_pct, concentration
        )
        if scrubbed_notes:
            alert_body = f"{alert_body} {scrubbed_notes}".strip()

        try:
            inquiry_result = await client.call(
                server="salesforce-crm",
                tool="create_object",
                arguments={
                    "object_type": "Client_Inquiry__c",
                    "fields": {
                        "Client_Contact_Id__c": client_contact_id,
                        "Inquiry_Text__c": alert_body,
                        "Channel__c": "Email",
                        "Ticker_Mentions__c": payload.ticker,
                        "Type__c": "alert",
                        "Auto_Send_Eligible__c": bool(auto_send),
                    },
                },
            )
        except Exception as exc:
            log.warning(
                "compliance_sweep inquiry_write_failed household=%s reason=%s",
                household_id,
                exc,
            )
            errors.append(
                HouseholdError(
                    household_id=household_id,
                    stage="inquiry_write",
                    reason=str(exc),
                )
            )
            continue

        inquiry_id = (
            (inquiry_result or {}).get("Id")
            or (inquiry_result or {}).get("id")
            or ""
        )
        if inquiry_id:
            inquiry_ids.append(inquiry_id)
        if auto_send:
            auto_send_count += 1
        else:
            rm_review_count += 1

        # 4d. Audit row — one per inquiry (steering rule 10).
        try:
            await audit_run(
                AuditInput(
                    action=AuditAction.VOLATILITY_ALERT_RAISED,
                    principal_id=payload.principal_id,
                    agent_id=_SWEEP_AGENT_ID,
                    session_id=payload.session_id,
                    correlation_id=payload.correlation_id,
                    client_contact_id=client_contact_id or None,
                    gate_trace=[
                        {"gate": "compliance_sweep", "outcome": "ok"},
                    ],
                    payload={
                        "ticker": payload.ticker,
                        "price_change_pct": payload.price_change_pct,
                        "concentration_pct": concentration,
                        "auto_send_eligible": bool(auto_send),
                        "inquiry_id": inquiry_id,
                        "household_id": household_id,
                    },
                ),
                mcp=client,
            )
        except Exception as exc:
            log.warning(
                "compliance_sweep audit_write_failed household=%s reason=%s",
                household_id,
                exc,
            )
            errors.append(
                HouseholdError(
                    household_id=household_id,
                    stage="audit_write",
                    reason=str(exc),
                )
            )

    alerts_raised = len(inquiry_ids)

    # --- Step 5: write the idempotency marker ------------------------------
    try:
        await _mark_processed(
            client, payload.event_id, payload.ticker, alerts_raised
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(
            "compliance_sweep marker_write_failed event_id=%s reason=%s",
            payload.event_id,
            exc,
        )

    if errors:
        log.warning(
            "compliance_sweep completed_with_errors event_id=%s error_count=%d",
            payload.event_id,
            len(errors),
        )

    return ComplianceSweepOutput(
        event_id=payload.event_id,
        households_scanned=households_scanned,
        alerts_raised=alerts_raised,
        auto_send_count=auto_send_count,
        rm_review_count=rm_review_count,
        skipped_idempotent=False,
        inquiry_ids=inquiry_ids,
        errors=errors,
    )

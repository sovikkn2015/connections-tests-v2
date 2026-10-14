"""mulesoft_api.run — SINGLE choke point for all MuleSoft write operations.

Steering rule 1: every MuleSoft call flows through this skill. No other code
path may call the mulesoft-actions MCP server directly.

Methods:
  - submit_order, cancel_order, modify_order
  - initiate_wire   (with OFAC SDN screening BEFORE the wire leaves)
  - order_status_webhook   (inbound webhook fan-out record)

Modes (steering rules 14-16):
  - mock     (default): deterministic realistic shapes, no network.
  - sandbox:  routes via mulesoft-actions MCP to an Anypoint sandbox.
  - production: routes via mulesoft-actions MCP to production Anypoint.

Mode is read from MULESOFT_MODE env. Unknown/missing -> mock.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, MCPError, get_shared_mock_client


_OFAC_STUB_PATH = Path(__file__).parent / "ofac_sdn_stub.json"


def _load_ofac() -> List[Dict[str, Any]]:
    override = os.getenv("OFAC_SDN_PATH")
    target = Path(override) if override else _OFAC_STUB_PATH
    with open(target, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("entries", [])


_OFAC_ENTRIES = _load_ofac()


def reload_ofac(path: Optional[Path] = None) -> None:
    """Hot-reload OFAC entries (tests + prod rotation)."""
    global _OFAC_ENTRIES
    env_override = os.getenv("OFAC_SDN_PATH")
    target = path or (Path(env_override) if env_override else _OFAC_STUB_PATH)
    with open(target, "r", encoding="utf-8") as fh:
        _OFAC_ENTRIES = json.load(fh).get("entries", [])


def _screen_ofac(beneficiary_name: str) -> Optional[Dict[str, Any]]:
    """Case-insensitive substring + alias match against SDN entries."""
    target = (beneficiary_name or "").upper()
    if not target:
        return None
    for entry in _OFAC_ENTRIES:
        names = [entry.get("name", ""), *entry.get("aliases", [])]
        for name in names:
            if name and name.upper() in target:
                return entry
    return None


class MuleSoftMethod(str, Enum):
    SUBMIT_ORDER = "submit_order"
    CANCEL_ORDER = "cancel_order"
    MODIFY_ORDER = "modify_order"
    INITIATE_WIRE = "initiate_wire"
    ORDER_STATUS_WEBHOOK = "order_status_webhook"


class MuleSoftMode(str, Enum):
    MOCK = "mock"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


def resolve_mode() -> MuleSoftMode:
    """Read MULESOFT_MODE; default sandbox (CloudHub is live)."""
    raw = (os.getenv("MULESOFT_MODE") or "sandbox").strip().lower()
    try:
        return MuleSoftMode(raw)
    except ValueError:
        return MuleSoftMode.SANDBOX


class MuleSoftInput(BaseModel):
    """Single entry point for every method; `args` is method-specific.

    Writes require `hitl_approval` (belt over suspenders for steering rule 2).
    """

    method: MuleSoftMethod
    args: Dict[str, Any] = Field(default_factory=dict)

    hitl_approval: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Approval object from hitl.verify — required for writes. "
            "Carries plan_hash + user_id; logged via audit (hashed)."
        ),
    )

    principal_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    client_contact_id: Optional[str] = None

    @model_validator(mode="after")
    def _writes_require_approval(self) -> "MuleSoftInput":
        write_methods = {
            MuleSoftMethod.SUBMIT_ORDER,
            MuleSoftMethod.CANCEL_ORDER,
            MuleSoftMethod.MODIFY_ORDER,
            MuleSoftMethod.INITIATE_WIRE,
        }
        if self.method in write_methods and self.hitl_approval is None:
            raise ValueError(
                f"method {self.method.value} requires an hitl_approval — "
                "steering rule 2."
            )
        return self

    model_config = {"frozen": True}


class MuleSoftOutput(BaseModel):
    method: MuleSoftMethod
    mode: MuleSoftMode
    success: bool
    mulesoft_reference: Optional[str] = None
    vendor_reference: Optional[str] = None
    audit_row_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    ofac_screening: Optional[Dict[str, Any]] = Field(
        None,
        description="Populated for initiate_wire with {screened: bool, hit: ?entry}.",
    )
    model_config = {"frozen": True}


def _mock_submit_order(args: Dict[str, Any]) -> Dict[str, Any]:
    order_id = f"ALPACA-{uuid4().hex[:8]}"
    return {
        "mulesoft_reference": f"MS-TRD-{uuid4().hex[:8]}",
        "vendor_reference": order_id,
        "data": {
            "order_id": order_id,
            "ticker": args.get("ticker"),
            "qty": args.get("qty"),
            "side": args.get("side"),
            "status": "accepted",
            "filled_avg_price": None,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _mock_cancel_order(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mulesoft_reference": f"MS-CANCEL-{uuid4().hex[:8]}",
        "vendor_reference": args.get("order_id"),
        "data": {
            "order_id": args.get("order_id"),
            "status": "canceled",
            "canceled_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _mock_modify_order(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mulesoft_reference": f"MS-MOD-{uuid4().hex[:8]}",
        "vendor_reference": args.get("order_id"),
        "data": {
            "order_id": args.get("order_id"),
            "new_limit_price": args.get("limit_price"),
            "status": "replaced",
            "modified_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _mock_initiate_wire(args: Dict[str, Any]) -> Dict[str, Any]:
    wire_id = f"WIRE-{uuid4().hex[:8]}"
    return {
        "mulesoft_reference": f"MS-WIRE-{uuid4().hex[:8]}",
        "vendor_reference": wire_id,
        "data": {
            "wire_id": wire_id,
            "amount_usd": args.get("amount_usd"),
            "beneficiary_name": args.get("beneficiary_name"),
            "beneficiary_bank": args.get("beneficiary_bank"),
            "status": "initiated",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
            "settles_t_plus_1": True,
        },
    }


def _mock_webhook(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mulesoft_reference": f"MS-HOOK-{uuid4().hex[:8]}",
        "vendor_reference": args.get("order_id"),
        "data": {
            "order_id": args.get("order_id"),
            "status": args.get("status", "filled"),
            "filled_qty": args.get("filled_qty"),
            "filled_avg_price": args.get("filled_avg_price"),
            "received_at": datetime.now(timezone.utc).isoformat(),
        },
    }


_MOCK_HANDLERS = {
    MuleSoftMethod.SUBMIT_ORDER: _mock_submit_order,
    MuleSoftMethod.CANCEL_ORDER: _mock_cancel_order,
    MuleSoftMethod.MODIFY_ORDER: _mock_modify_order,
    MuleSoftMethod.INITIATE_WIRE: _mock_initiate_wire,
    MuleSoftMethod.ORDER_STATUS_WEBHOOK: _mock_webhook,
}


def _action_for(method: MuleSoftMethod, success: bool) -> AuditAction:
    if not success:
        return (
            AuditAction.WIRE_BLOCKED
            if method is MuleSoftMethod.INITIATE_WIRE
            else AuditAction.TRADE_REJECTED
        )
    return {
        MuleSoftMethod.SUBMIT_ORDER: AuditAction.TRADE_SUBMITTED,
        MuleSoftMethod.CANCEL_ORDER: AuditAction.TRADE_CANCELLED,
        MuleSoftMethod.MODIFY_ORDER: AuditAction.TRADE_MODIFIED,
        MuleSoftMethod.INITIATE_WIRE: AuditAction.WIRE_INITIATED,
        MuleSoftMethod.ORDER_STATUS_WEBHOOK: AuditAction.TRADE_SUBMITTED,
    }[method]


async def run(
    payload: MuleSoftInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> MuleSoftOutput:
    """Execute a MuleSoft method. Routes by MULESOFT_MODE + performs audit."""
    client = mcp or get_shared_mock_client()
    mode = resolve_mode()

    ofac_screening: Optional[Dict[str, Any]] = None
    if payload.method is MuleSoftMethod.INITIATE_WIRE:
        beneficiary = str(payload.args.get("beneficiary_name", ""))
        hit = _screen_ofac(beneficiary)
        ofac_screening = {"screened": True, "hit": hit}
        if hit is not None:
            audit = await audit_run(
                AuditInput(
                    action=AuditAction.WIRE_BLOCKED,
                    principal_id=payload.principal_id,
                    agent_id=payload.agent_id,
                    session_id=payload.session_id,
                    correlation_id=payload.correlation_id,
                    client_contact_id=payload.client_contact_id,
                    approver_id=(payload.hitl_approval or {}).get("user_id"),
                    gate_trace=[
                        {"gate": "ofac_sdn", "outcome": "blocked",
                         "sdn_id": hit.get("sdn_id"),
                         "program": hit.get("program")}
                    ],
                    payload={
                        "method": payload.method.value,
                        "beneficiary_name": beneficiary,
                        "mode": mode.value,
                    },
                ),
                mcp=client,
            )
            return MuleSoftOutput(
                method=payload.method,
                mode=mode,
                success=False,
                audit_row_id=audit.audit_row_id,
                error=f"ofac_sdn_hit:{hit.get('sdn_id')}",
                ofac_screening=ofac_screening,
            )

    result_payload: Dict[str, Any]
    err: Optional[str] = None
    try:
        if mode is MuleSoftMode.MOCK:
            handler = _MOCK_HANDLERS[payload.method]
            result_payload = handler(payload.args)
        else:
            result_payload = await client.call(
                server="mulesoft-actions",
                tool=payload.method.value,
                arguments={
                    "args": payload.args,
                    "principal_id": payload.principal_id,
                    "approval": payload.hitl_approval or {},
                    "mode": mode.value,
                },
            )
    except MCPError as exc:
        err = f"mcp_error:{exc.reason}"
        result_payload = {"error": err}

    success = err is None
    linked_trade_id = (
        result_payload.get("vendor_reference")
        if payload.method in (
            MuleSoftMethod.SUBMIT_ORDER,
            MuleSoftMethod.CANCEL_ORDER,
            MuleSoftMethod.MODIFY_ORDER,
            MuleSoftMethod.ORDER_STATUS_WEBHOOK,
        )
        else None
    )
    linked_wire_id = (
        result_payload.get("vendor_reference")
        if payload.method is MuleSoftMethod.INITIATE_WIRE
        else None
    )

    audit = await audit_run(
        AuditInput(
            action=_action_for(payload.method, success),
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            client_contact_id=payload.client_contact_id,
            approver_id=(payload.hitl_approval or {}).get("user_id"),
            linked_trade_id=linked_trade_id,
            linked_wire_id=linked_wire_id,
            mulesoft_reference=result_payload.get("mulesoft_reference"),
            gate_trace=[
                {"gate": "mulesoft_api", "method": payload.method.value,
                 "mode": mode.value, "outcome": "success" if success else "error"}
            ],
            payload={
                "method": payload.method.value,
                "mode": mode.value,
                "args_keys": sorted(payload.args.keys()),
                "vendor_reference": result_payload.get("vendor_reference"),
            },
        ),
        mcp=client,
    )

    return MuleSoftOutput(
        method=payload.method,
        mode=mode,
        success=success,
        mulesoft_reference=result_payload.get("mulesoft_reference"),
        vendor_reference=result_payload.get("vendor_reference"),
        audit_row_id=audit.audit_row_id,
        data=result_payload.get("data", {}),
        error=err,
        ofac_screening=ofac_screening,
    )

"""Tool dispatcher for M13 FIX Bridge.

Every MCP call through ``POST /tools/call`` funnels here. The
dispatcher handles:

1. AID verification via the injected ``AidVerifier`` (Spec §R13).
2. Tool resolution — unknown tool → ``unknown_tool`` error.
3. pydantic validation — bad args → ``invalid_arguments``.
4. Role gate for ``fix.kill_switch`` — non-``trading_supervisor`` →
   ``unauthorized``.
5. Kill-switch gate for outbound order tools (Spec §R7).
6. ``FIX_ENABLED=false`` gate for outbound order tools (Spec §R4.1).
7. Tool handler invocation. AdapterError → canonical MCP envelope.
   Unhandled exceptions → ``adapter_internal_error``.
8. Audit emission per tool call (success + failure).
9. For ``fix.order_new`` specifically: correlate the
   outbound cl_ord_id → trader_aid in the drop-copy correlator so
   future inbound ExecReports resolve.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping, Optional

from pydantic import BaseModel, ValidationError

from m13_fix_bridge.aid_verify import (
    AidClaims,
    AidVerifier,
    AidVerifyError,
)
from m13_fix_bridge.audit import AuditEvent, StdoutAuditEmitter
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.drop_copy import DropCopyEmitter
from m13_fix_bridge.models import (
    KillSwitchInput,
    KillSwitchResponse,
    NewOrderSingleInput,
    OrderCancelInput,
    OrderCancelReplaceInput,
    OrderStatusInput,
    SessionStatusInput,
    SessionStatusResponse,
)


# ---------------------------------------------------------------------------
# Canonical error code vocabulary (Spec §2.9)
# ---------------------------------------------------------------------------

_ERROR_CODES = frozenset(
    {
        "invalid_arguments",
        "unknown_tool",
        "unauthorized",
        "kill_switch_active",
        "session_not_authorized",
        "session_not_found",
        "venue_rejected",
        "venue_timeout",
        "venue_disconnected",
        "fix_enabled_false",
        "adapter_internal_error",
        "vendor_error",
    }
)

_RETRYABLE_CODES = frozenset(
    {"venue_timeout", "venue_disconnected", "vendor_error"}
)


class AdapterError(Exception):
    """Canonical error surfaced to the MCP caller."""

    __slots__ = ("code", "_msg", "retryable")

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: Optional[bool] = None,
    ) -> None:
        if code not in _ERROR_CODES:
            raise ValueError(f"unknown error code: {code!r}")
        super().__init__(message)
        self.code = code
        self._msg = message
        self.retryable = (
            code in _RETRYABLE_CODES if retryable is None else bool(retryable)
        )

    @property
    def message(self) -> str:
        return self._msg


# ---------------------------------------------------------------------------
# Tool catalog
# ---------------------------------------------------------------------------

ToolHandler = Callable[
    [BaseModel, AidClaims],
    Awaitable[dict[str, Any]],
]


class _ToolSpec:
    __slots__ = ("name", "description", "input_model")

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model


# Static tool catalog — input_model drives JSON schema generation.
_TOOLS: dict[str, _ToolSpec] = {
    "fix.order_new": _ToolSpec(
        name="fix.order_new",
        description="Submit a FIX 4.4 NewOrderSingle (MsgType D).",
        input_model=NewOrderSingleInput,
    ),
    "fix.order_cancel": _ToolSpec(
        name="fix.order_cancel",
        description="Submit a FIX 4.4 OrderCancelRequest (MsgType F).",
        input_model=OrderCancelInput,
    ),
    "fix.order_cancel_replace": _ToolSpec(
        name="fix.order_cancel_replace",
        description="Submit a FIX 4.4 OrderCancelReplaceRequest (MsgType G).",
        input_model=OrderCancelReplaceInput,
    ),
    "fix.order_status": _ToolSpec(
        name="fix.order_status",
        description="Submit a FIX 4.4 OrderStatusRequest (MsgType H).",
        input_model=OrderStatusInput,
    ),
    "fix.session_status": _ToolSpec(
        name="fix.session_status",
        description="Return per-venue FIX session state.",
        input_model=SessionStatusInput,
    ),
    "fix.kill_switch": _ToolSpec(
        name="fix.kill_switch",
        description=(
            "Toggle the global or per-venue kill switch. Requires "
            "role=trading_supervisor on the AID."
        ),
        input_model=KillSwitchInput,
    ),
}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class Dispatcher:
    """Central tool dispatcher.

    Constructed once at app startup. ``call`` is the single entry point
    used by the FastAPI ``/tools/call`` route handler AND by integration
    tests that bypass HTTP.
    """

    _ORDER_TOOLS = frozenset(
        {
            "fix.order_new",
            "fix.order_cancel",
            "fix.order_cancel_replace",
            "fix.order_status",
        }
    )

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        kill_switch: KillSwitch,
        audit: StdoutAuditEmitter,
        verify_aid: AidVerifier,
        drop_copy: DropCopyEmitter,
        fix_enabled: bool,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._sm = session_manager
        self._ks = kill_switch
        self._audit = audit
        self._verify_aid = verify_aid
        self._drop_copy = drop_copy
        self._fix_enabled = bool(fix_enabled)
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))

    # ------------------------------------------------------------------
    # MCP surface helpers
    # ------------------------------------------------------------------

    @staticmethod
    def catalog() -> list[dict[str, Any]]:
        """Return the tool catalog shape for ``POST /tools/list``."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_model.model_json_schema(),
            }
            for spec in _TOOLS.values()
        ]

    async def call(
        self,
        *,
        tool: str,
        arguments: Mapping[str, Any],
        aid_token: str | None,
    ) -> dict[str, Any]:
        """Dispatch a single tool call. Returns an MCP envelope dict.

        Success: ``{"isError": False, "content": <dict>}``
        Failure: ``{"isError": True, "errorCode": "...", "content":
                   [{"type":"text","text":"..."}], "retryable": bool}``
        """
        started_ms = self._clock_ms()

        # 1. AID verify
        if not aid_token:
            return self._error_envelope(
                "unauthorized",
                "missing X-Agent-AID header",
                started_ms=started_ms,
                tool=tool,
                claims=None,
            )
        try:
            claims = self._verify_aid.verify(aid_token)
        except AidVerifyError as exc:
            return self._error_envelope(
                "unauthorized",
                f"aid verify failed: {exc}",
                started_ms=started_ms,
                tool=tool,
                claims=None,
            )

        # 2. Tool resolve
        spec = _TOOLS.get(tool)
        if spec is None:
            return self._error_envelope(
                "unknown_tool",
                f"unknown tool: {tool!r}",
                started_ms=started_ms,
                tool=tool,
                claims=claims,
            )

        # 3. Pydantic validation
        try:
            validated = spec.input_model.model_validate(arguments)
        except ValidationError as ve:
            return self._error_envelope(
                "invalid_arguments",
                f"argument validation failed: {ve.error_count()} error(s)",
                started_ms=started_ms,
                tool=tool,
                claims=claims,
            )

        # 4. Role gate for kill_switch
        if tool == "fix.kill_switch" and claims.role != "trading_supervisor":
            return self._error_envelope(
                "unauthorized",
                "role=trading_supervisor required",
                started_ms=started_ms,
                tool=tool,
                claims=claims,
            )

        # 5. Kill-switch gate for order tools
        if tool in self._ORDER_TOOLS:
            venue = getattr(validated, "venue", None)
            if venue is not None and self._ks.is_blocked(venue):
                return self._error_envelope(
                    "kill_switch_active",
                    f"kill switch active for venue={venue!r}",
                    started_ms=started_ms,
                    tool=tool,
                    claims=claims,
                    venue=venue,
                )

        # 6. FIX_ENABLED gate for order tools
        if tool in self._ORDER_TOOLS and not self._fix_enabled:
            return self._error_envelope(
                "fix_enabled_false",
                "FIX_ENABLED=false; order tools disabled",
                started_ms=started_ms,
                tool=tool,
                claims=claims,
                venue=getattr(validated, "venue", None),
            )

        # 7. Handler invocation
        try:
            content = await self._dispatch_tool(tool, validated, claims)
        except AdapterError as ae:
            return self._error_envelope(
                ae.code,
                ae.message,
                started_ms=started_ms,
                tool=tool,
                claims=claims,
                venue=getattr(validated, "venue", None),
                cl_ord_id=getattr(validated, "cl_ord_id", None),
            )
        except Exception as exc:  # pragma: no cover — bug path
            return self._error_envelope(
                "adapter_internal_error",
                f"unhandled exception: {type(exc).__name__}",
                started_ms=started_ms,
                tool=tool,
                claims=claims,
            )

        # 8. Audit success
        duration_ms = max(0, self._clock_ms() - started_ms)
        self._audit.tool_audit(
            tool=tool,
            outcome="success",
            duration_ms=duration_ms,
            trader_aid=claims.aid,
            firm_id=claims.firm_id,
            tenant_id=claims.tenant_id,
            venue=getattr(validated, "venue", None),
            cl_ord_id=content.get("cl_ord_id") if isinstance(content, dict) else None,
            seq_num_out=(
                content.get("seq_num_out") if isinstance(content, dict) else None
            ),
        )

        return {"isError": False, "content": content}

    # ------------------------------------------------------------------
    # Per-tool handlers
    # ------------------------------------------------------------------

    async def _dispatch_tool(
        self,
        tool: str,
        args: BaseModel,
        claims: AidClaims,
    ) -> dict[str, Any]:
        if tool == "fix.order_new":
            return await self._handle_order_new(args, claims)  # type: ignore[arg-type]
        if tool == "fix.order_cancel":
            return await self._handle_order_cancel(args, claims)  # type: ignore[arg-type]
        if tool == "fix.order_cancel_replace":
            return await self._handle_order_cancel_replace(args, claims)  # type: ignore[arg-type]
        if tool == "fix.order_status":
            return await self._handle_order_status(args, claims)  # type: ignore[arg-type]
        if tool == "fix.session_status":
            return await self._handle_session_status(args, claims)  # type: ignore[arg-type]
        if tool == "fix.kill_switch":
            return await self._handle_kill_switch(args, claims)  # type: ignore[arg-type]
        raise AdapterError("unknown_tool", f"unhandled tool: {tool!r}")

    async def _handle_order_new(
        self, args: NewOrderSingleInput, claims: AidClaims
    ) -> dict[str, Any]:
        venue = args.venue
        engine = self._sm.engine
        if not engine.has_venue(venue):
            raise AdapterError("session_not_found", f"unknown venue {venue!r}")
        st = self._sm.session_status(venue)
        if st is None or st.logon_status != "ACTIVE":
            raise AdapterError(
                "session_not_authorized",
                f"session for venue {venue!r} is not ACTIVE",
            )
        msg = args.model_dump(mode="json")
        try:
            resp = await engine.send_order_new(venue, msg)
        except Exception as exc:
            raise AdapterError("venue_rejected", f"engine rejected: {exc}") from exc
        # Correlate cl_ord_id → trader_aid for drop-copy.
        self._drop_copy.correlator.remember(args.cl_ord_id, claims.aid)
        return resp.model_dump(mode="json")

    async def _handle_order_cancel(
        self, args: OrderCancelInput, claims: AidClaims
    ) -> dict[str, Any]:
        return await self._simple_send(
            engine_fn="send_order_cancel",
            venue=args.venue,
            msg=args.model_dump(mode="json"),
        )

    async def _handle_order_cancel_replace(
        self, args: OrderCancelReplaceInput, claims: AidClaims
    ) -> dict[str, Any]:
        out = await self._simple_send(
            engine_fn="send_order_cancel_replace",
            venue=args.venue,
            msg=args.model_dump(mode="json"),
        )
        self._drop_copy.correlator.remember(args.cl_ord_id, claims.aid)
        return out

    async def _handle_order_status(
        self, args: OrderStatusInput, claims: AidClaims
    ) -> dict[str, Any]:
        return await self._simple_send(
            engine_fn="send_order_status",
            venue=args.venue,
            msg=args.model_dump(mode="json"),
        )

    async def _simple_send(
        self,
        *,
        engine_fn: str,
        venue: str,
        msg: dict[str, Any],
    ) -> dict[str, Any]:
        engine = self._sm.engine
        if not engine.has_venue(venue):
            raise AdapterError("session_not_found", f"unknown venue {venue!r}")
        st = self._sm.session_status(venue)
        if st is None or st.logon_status != "ACTIVE":
            raise AdapterError(
                "session_not_authorized",
                f"session for venue {venue!r} is not ACTIVE",
            )
        fn = getattr(engine, engine_fn)
        try:
            resp = await fn(venue, msg)
        except Exception as exc:
            raise AdapterError("venue_rejected", f"engine rejected: {exc}") from exc
        return resp.model_dump(mode="json")

    async def _handle_session_status(
        self, args: SessionStatusInput, claims: AidClaims
    ) -> dict[str, Any]:
        st = self._sm.session_status(args.venue)
        if st is None:
            raise AdapterError(
                "session_not_found", f"unknown venue {args.venue!r}"
            )
        return st.model_dump(mode="json")

    async def _handle_kill_switch(
        self, args: KillSwitchInput, claims: AidClaims
    ) -> dict[str, Any]:
        when = datetime.now(tz=timezone.utc)
        if args.scope == "global":
            entry = self._ks.set_global(
                args.state == "on", reason=args.reason, actor_aid=claims.aid
            )
        else:
            assert args.venue is not None  # pydantic model invariant
            entry = self._ks.set_venue(
                args.venue,
                args.state == "on",
                reason=args.reason,
                actor_aid=claims.aid,
            )
        # If global kill just flipped ON, drive an emergency session shutdown.
        if args.scope == "global" and args.state == "on":
            await self._sm.engine.close()
        self._audit.emit(_kill_switch_event(args, claims, when))
        resp = KillSwitchResponse(
            scope=args.scope,
            venue=args.venue,
            state=args.state,
            set_at=when,
            actor_aid=claims.aid,
            reason=args.reason,
        )
        return resp.model_dump(mode="json")

    # ------------------------------------------------------------------
    # Error envelope helpers
    # ------------------------------------------------------------------

    def _error_envelope(
        self,
        code: str,
        message: str,
        *,
        started_ms: int,
        tool: str,
        claims: AidClaims | None,
        venue: str | None = None,
        cl_ord_id: str | None = None,
    ) -> dict[str, Any]:
        duration_ms = max(0, self._clock_ms() - started_ms)
        self._audit.tool_audit(
            tool=tool,
            outcome="failure",
            duration_ms=duration_ms,
            trader_aid=claims.aid if claims else None,
            firm_id=claims.firm_id if claims else None,
            tenant_id=claims.tenant_id if claims else None,
            venue=venue,
            cl_ord_id=cl_ord_id,
            error_code=code,
        )
        retryable = code in _RETRYABLE_CODES
        return {
            "isError": True,
            "errorCode": code,
            "content": [{"type": "text", "text": message}],
            "retryable": retryable,
        }


def _kill_switch_event(args, claims, when):
    """Build an AuditEvent for kill-switch toggles (fallback path)."""
    return AuditEvent(
        kind="fix.session_event",
        fields={
            "event": "kill_switch_toggled",
            "scope": args.scope,
            "venue": args.venue,
            "state": args.state,
            "actor_aid": claims.aid,
            "reason": args.reason,
            "set_at": when.isoformat().replace("+00:00", "Z"),
        },
    )


__all__ = ["AdapterError", "Dispatcher"]

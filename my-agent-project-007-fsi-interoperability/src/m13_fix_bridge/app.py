"""FastAPI MCP server factory for M13 FIX Bridge.

Three endpoints only (Spec §R1):

* ``GET /``              — health + server info
* ``POST /tools/list``   — tool catalog
* ``POST /tools/call``   — dispatch

Every tool call REQUIRES ``X-Agent-AID`` header (Spec §R13). The
dispatcher owns AID verification, role gate, kill-switch gate, and
audit emission — this module is purely the HTTP shell.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from m13_fix_bridge.aid_verify import AidVerifier, StaticAidVerifier
from m13_fix_bridge.audit import StdoutAuditEmitter
from m13_fix_bridge.client.fake_engine import FakeFixEngine
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.protocol import FixEngineProtocol
from m13_fix_bridge.client.session import FileSeqnumStore
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.config import FixConfig, load_config
from m13_fix_bridge.dispatcher import Dispatcher
from m13_fix_bridge.drop_copy import DropCopyEmitter
from m13_fix_bridge.health import health_status


_SERVER_NAME = "m13-fix-bridge"
_SERVER_VERSION = "0.1.0"
_VENDOR = "fix-4.4-generic"


def create_app(
    *,
    config: FixConfig | None = None,
    engine: FixEngineProtocol | None = None,
    audit: StdoutAuditEmitter | None = None,
    verify_aid: AidVerifier | None = None,
    kill_switch: KillSwitch | None = None,
    session_manager: SessionManager | None = None,
    drop_copy: DropCopyEmitter | None = None,
    account_salt: bytes | None = None,
) -> FastAPI:
    """Assemble a FastAPI app around an M13 dispatcher.

    All dependencies are injectable so tests can override them
    individually. Production wiring is in ``startup.py``.
    """
    cfg = config if config is not None else load_config()
    ae = audit if audit is not None else StdoutAuditEmitter()
    aid_verifier = verify_aid if verify_aid is not None else StaticAidVerifier.empty()

    # Engine / KillSwitch / SessionManager / DropCopy all have sane
    # in-memory defaults so tests can omit them.
    eng = engine if engine is not None else FakeFixEngine()
    ks = kill_switch if kill_switch is not None else KillSwitch(cfg.kill_switch_state_path)
    if session_manager is not None:
        sm = session_manager
    else:
        store = FileSeqnumStore(cfg.seqnum_store_dir)
        sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    dc_salt = account_salt if account_salt is not None else b"m13-test-salt-default-32-bytes!!"
    dc = drop_copy if drop_copy is not None else DropCopyEmitter(
        audit=ae,
        account_salt=dc_salt,
        enabled=cfg.drop_copy_enabled,
    )

    # Bridge inbound ExecReports / CancelRejects through drop-copy.
    async def _on_inbound(venue: str, kind: str, msg: dict[str, Any]) -> None:
        tenant_id = msg.get("tenant_id", "_unknown")
        if kind == "exec_report":
            dc.on_exec_report(venue=venue, report=msg, tenant_id=tenant_id)
        elif kind == "cancel_reject":
            dc.on_cancel_reject(venue=venue, reject=msg, tenant_id=tenant_id)

    sm.set_inbound_handler(_on_inbound)

    dispatcher = Dispatcher(
        session_manager=sm,
        kill_switch=ks,
        audit=ae,
        verify_aid=aid_verifier,
        drop_copy=dc,
        fix_enabled=cfg.fix_enabled,
    )

    app = FastAPI(
        title=_SERVER_NAME,
        version=_SERVER_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Attach handles for test introspection.
    app.state.config = cfg
    app.state.dispatcher = dispatcher
    app.state.session_manager = sm
    app.state.kill_switch = ks
    app.state.audit = ae
    app.state.drop_copy = dc

    @app.get("/")
    async def root() -> JSONResponse:
        status = health_status(session_manager=sm, fix_enabled=cfg.fix_enabled)
        body = {
            "name": _SERVER_NAME,
            "version": _SERVER_VERSION,
            "vendor": _VENDOR,
            "capabilities": {
                "tools": [t["name"] for t in Dispatcher.catalog()],
                "fix_enabled": cfg.fix_enabled,
                "drop_copy_enabled": cfg.drop_copy_enabled,
            },
            "status": "ok" if status.ok else "degraded",
            "checks": dict(status.checks),
        }
        return JSONResponse(status_code=200 if status.ok else 503, content=body)

    @app.post("/tools/list")
    async def tools_list() -> dict[str, Any]:
        return {"tools": Dispatcher.catalog()}

    @app.post("/tools/call")
    async def tools_call(
        request: Request,
        x_agent_aid: Optional[str] = Header(default=None, alias="X-Agent-AID"),
    ) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=200,
                content={
                    "isError": True,
                    "errorCode": "invalid_arguments",
                    "content": [{"type": "text", "text": "body is not valid JSON"}],
                    "retryable": False,
                },
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=200,
                content={
                    "isError": True,
                    "errorCode": "invalid_arguments",
                    "content": [{"type": "text", "text": "body must be a JSON object"}],
                    "retryable": False,
                },
            )
        name = payload.get("name")
        arguments = payload.get("arguments", {})
        if not isinstance(name, str) or not name:
            return JSONResponse(
                status_code=200,
                content={
                    "isError": True,
                    "errorCode": "invalid_arguments",
                    "content": [{"type": "text", "text": "missing 'name'"}],
                    "retryable": False,
                },
            )
        if not isinstance(arguments, dict):
            return JSONResponse(
                status_code=200,
                content={
                    "isError": True,
                    "errorCode": "invalid_arguments",
                    "content": [{"type": "text", "text": "'arguments' must be an object"}],
                    "retryable": False,
                },
            )

        envelope = await dispatcher.call(
            tool=name, arguments=arguments, aid_token=x_agent_aid
        )
        http_status = (
            500 if envelope.get("errorCode") == "adapter_internal_error" else 200
        )
        return JSONResponse(status_code=http_status, content=envelope)

    return app


__all__ = ["create_app"]

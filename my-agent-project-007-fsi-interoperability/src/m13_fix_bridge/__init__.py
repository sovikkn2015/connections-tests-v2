"""
M13 FIX Bridge — Stateful FIX 4.4 TCP sessions exposed as MCP tools.

This module is a PEER of M11 (not a child). Steering Rule 11: M13 is a
SEPARATE module from M11 — stateful (FIX sessions have sequence numbers
and state), uses StatefulSet + PersistentVolume, not Deployment.

Module boundary (Rule 33):
* No imports from M1, M2/M4, M5, M6, M7, M8, M9, M10, M11, M12.
* No imports from ``m11_python_adapters_shared`` (M11 family infra).
* Allowed: stdlib, pydantic, fastapi, starlette, uvicorn (runtime),
  simplefix (lazy in real_engine.py only), typing_extensions.

Public surface exposed here is consumed by ``app.py`` + tests.
"""

from __future__ import annotations

from m13_fix_bridge.app import create_app
from m13_fix_bridge.audit import AuditEvent, StdoutAuditEmitter
from m13_fix_bridge.config import FixConfig, load_config
from m13_fix_bridge.aid_verify import (
    AidClaims,
    AidVerifier,
    AidVerifyError,
    HmacAidVerifier,
    StaticAidVerifier,
)
from m13_fix_bridge.drop_copy import DropCopyEmitter
from m13_fix_bridge.dispatcher import AdapterError, Dispatcher
from m13_fix_bridge.client.fake_engine import FakeFixEngine
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.protocol import FixEngineProtocol
from m13_fix_bridge.client.session import FileSeqnumStore, FixSession, SessionState
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.models import (
    ExecReport,
    FixOrdStatus,
    FixOrdType,
    FixSide,
    FixTimeInForce,
    KillSwitchInput,
    KillSwitchResponse,
    NewOrderSingleInput,
    OrderCancelInput,
    OrderCancelReplaceInput,
    OrderResponse,
    OrderStatusInput,
    SessionStatusInput,
    SessionStatusResponse,
    VenueConfig,
)

__all__ = [
    # app
    "create_app",
    # config / env
    "FixConfig",
    "load_config",
    # audit
    "AuditEvent",
    "StdoutAuditEmitter",
    # AID
    "AidClaims",
    "AidVerifier",
    "AidVerifyError",
    "HmacAidVerifier",
    "StaticAidVerifier",
    # drop-copy
    "DropCopyEmitter",
    # dispatcher / errors
    "AdapterError",
    "Dispatcher",
    # engine
    "FixEngineProtocol",
    "FakeFixEngine",
    "SessionManager",
    "FixSession",
    "FileSeqnumStore",
    "SessionState",
    "KillSwitch",
    # models
    "ExecReport",
    "FixOrdStatus",
    "FixOrdType",
    "FixSide",
    "FixTimeInForce",
    "KillSwitchInput",
    "KillSwitchResponse",
    "NewOrderSingleInput",
    "OrderCancelInput",
    "OrderCancelReplaceInput",
    "OrderResponse",
    "OrderStatusInput",
    "SessionStatusInput",
    "SessionStatusResponse",
    "VenueConfig",
]

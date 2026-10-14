"""
M13 FIX Bridge — FastAPI application.

Combines MCP endpoints (GET /, POST /tools/list, POST /tools/call)
with session management REST endpoints.
M6 gateway calls M13 via MCP — same interface as M11 adapters.

Run: uvicorn app:app --host 0.0.0.0 --port 8030

No cross-module imports. No credentials in code.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

try:
    from .mcp_wrapper import create_mcp_server
    from .session_manager import FIXSessionManager
    from .models import FIXBridgeConfig
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent

    _mcp_spec = importlib.util.spec_from_file_location("fix_mcp_local", _base / "mcp_wrapper.py")
    _mcp_mod = importlib.util.module_from_spec(_mcp_spec)
    _mcp_spec.loader.exec_module(_mcp_mod)
    create_mcp_server = _mcp_mod.create_mcp_server

    _sm_spec = importlib.util.spec_from_file_location("fix_sm_local_app", _base / "session_manager.py")
    _sm_mod = importlib.util.module_from_spec(_sm_spec)
    _sm_spec.loader.exec_module(_sm_mod)
    FIXSessionManager = _sm_mod.FIXSessionManager

    _m_spec = importlib.util.spec_from_file_location("fix_models_local_app", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    FIXBridgeConfig = _m_mod.FIXBridgeConfig

logger = logging.getLogger("m13_fix_bridge.app")

# ---------------------------------------------------------------------------
# Build MCP app from _shared factory (GET /, POST /tools/list, POST /tools/call)
# ---------------------------------------------------------------------------
_mcp_server = create_mcp_server()
app = _mcp_server.build_app()

# Session manager instance (in-memory for dev/test)
_session_mgr = FIXSessionManager()


# ---------------------------------------------------------------------------
# Session management REST endpoints
# ---------------------------------------------------------------------------


@app.post("/session/connect")
async def session_connect(config: FIXBridgeConfig) -> dict:
    """Create and connect a FIX session."""
    try:
        session = _session_mgr.create_session(config)
        session = _session_mgr.connect(session.session_id)
        return session.model_dump()
    except Exception as e:
        logger.error("Session connect failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/session/disconnect")
async def session_disconnect(session_id: str) -> dict:
    """Disconnect a FIX session (send Logout)."""
    try:
        session = _session_mgr.disconnect(session_id)
        return session.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/session/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get session state and sequence numbers."""
    session = _session_mgr.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session.model_dump()


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "module": "m13-fix-bridge", "version": "1.0.0"}

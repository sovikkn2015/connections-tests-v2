"""
Memory Service — FastAPI REST endpoints.

POST /memory/write                    — Write entry to a layer
POST /memory/read                     — Read entries with MNPI filtering
GET  /memory/conversation/{client_id} — Get L1 working memory
GET  /health                          — Health check

No cross-module imports. No credentials in code.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .memory_store import MemoryService
    from .models import MemoryEntry, MemoryLayer, MemoryQuery
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent
    _s_spec = importlib.util.spec_from_file_location("memory_store_local", _base / "memory_store.py")
    _s_mod = importlib.util.module_from_spec(_s_spec)
    _s_spec.loader.exec_module(_s_mod)
    MemoryService = _s_mod.MemoryService
    _m_spec = importlib.util.spec_from_file_location("memory_models_local2", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    MemoryEntry = _m_mod.MemoryEntry
    MemoryLayer = _m_mod.MemoryLayer
    MemoryQuery = _m_mod.MemoryQuery

logger = logging.getLogger("memory_service.app")


class WriteBody(BaseModel):
    """Request body for POST /memory/write."""
    layer: str = Field(..., description="Memory layer: L1-L6")
    entry: MemoryEntry


def create_app() -> FastAPI:
    """Create the Memory Service FastAPI application."""

    app = FastAPI(
        title="Memory Service",
        description="6-layer memory architecture with MNPI filtering. Per ARCH-09.",
        version="0.1.0",
    )

    svc = MemoryService()
    app.state.memory_service = svc

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "memory-service", "version": "0.1.0"}

    @app.post("/memory/write")
    async def write_memory(body: WriteBody):
        """Write an entry to a memory layer."""
        try:
            layer = MemoryLayer(body.layer)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid layer: {body.layer}")
        entry = svc.write(layer, body.entry)
        return entry.model_dump()

    @app.post("/memory/read")
    async def read_memory(query: MemoryQuery):
        """Read entries with MNPI filtering."""
        entries = svc.read(query)
        return [e.model_dump() for e in entries]

    @app.get("/memory/conversation/{client_id}")
    async def get_conversation(client_id: str, channel: Optional[str] = None):
        """Get L1 working memory for current conversation."""
        entries = svc.get_conversation_context(client_id, channel)
        return [e.model_dump() for e in entries]

    return app

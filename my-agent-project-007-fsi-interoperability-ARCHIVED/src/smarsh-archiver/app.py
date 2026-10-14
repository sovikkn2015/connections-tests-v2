"""
Smarsh Archiver — FastAPI REST endpoints.

POST /archive         — Archive a communication
GET  /archive/{id}    — Get archive record by ID
GET  /health          — Health check

No cross-module imports. No credentials in code.
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .archiver import SmarshArchiver
    from .models import SmarshConfig
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent
    _a_spec = importlib.util.spec_from_file_location("smarsh_archiver_local", _base / "archiver.py")
    _a_mod = importlib.util.module_from_spec(_a_spec)
    _a_spec.loader.exec_module(_a_mod)
    SmarshArchiver = _a_mod.SmarshArchiver
    _m_spec = importlib.util.spec_from_file_location("smarsh_models_local2", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    SmarshConfig = _m_mod.SmarshConfig

logger = logging.getLogger("smarsh_archiver.app")


class ArchiveBody(BaseModel):
    """Request body for POST /archive."""
    content: str = Field(..., min_length=1, description="Communication content to archive")
    content_type: str = Field(..., description="agent_response|meeting_summary|research_brief|trade_confirmation")
    metadata: dict = Field(default_factory=dict, description="Optional metadata")


def create_app() -> FastAPI:
    """Create the Smarsh Archiver FastAPI application."""

    app = FastAPI(
        title="Smarsh Archiver",
        description="FINRA Rule 17a-4 communication archiving. Phase 3 module per ARCH-09.",
        version="0.1.0",
    )

    archiver = SmarshArchiver()
    app.state.archiver = archiver

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "smarsh-archiver", "version": "0.1.0"}

    @app.post("/archive")
    async def archive_communication(body: ArchiveBody):
        """Archive a BD communication to Smarsh."""
        result = await archiver.archive_communication(
            content=body.content,
            content_type=body.content_type,
            metadata=body.metadata,
        )
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        return result.model_dump()

    @app.get("/archive/{record_id}")
    async def get_archive(record_id: str):
        """Get archive record by internal record ID."""
        record = await archiver.get_archive_status(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")
        return record.model_dump()

    return app

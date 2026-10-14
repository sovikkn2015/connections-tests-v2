"""
Onboarding Specialist — FastAPI REST endpoints.

POST /onboarding/start              — Start new onboarding session
POST /onboarding/{id}/collect-info  — Collect client information
POST /onboarding/{id}/approve       — HITL approve onboarding
GET  /onboarding/{id}               — Get session by ID
GET  /health                        — Health check

No cross-module imports. No credentials in code.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from .workflow import OnboardingWorkflow
    from .models import OnboardingRequest
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent
    _wf_spec = importlib.util.spec_from_file_location("onboarding_workflow_local", _base / "workflow.py")
    _wf_mod = importlib.util.module_from_spec(_wf_spec)
    _wf_spec.loader.exec_module(_wf_mod)
    OnboardingWorkflow = _wf_mod.OnboardingWorkflow
    _m_spec = importlib.util.spec_from_file_location("onboarding_models_local2", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    OnboardingRequest = _m_mod.OnboardingRequest

logger = logging.getLogger("onboarding_specialist.app")


class CollectInfoBody(BaseModel):
    """Request body for collect-info endpoint."""
    client_info: dict


class ApproveBody(BaseModel):
    """Request body for approve endpoint."""
    reviewer_id: str


def create_app() -> FastAPI:
    """Create the Onboarding Specialist FastAPI application."""

    app = FastAPI(
        title="Onboarding Specialist",
        description=(
            "Multi-session KYC workflow engine with mandatory HITL. "
            "Phase 3 module per ARCH-09."
        ),
        version="0.1.0",
    )

    wf = OnboardingWorkflow()
    app.state.workflow = wf

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "onboarding-specialist", "version": "0.1.0"}

    @app.post("/onboarding/start")
    async def start_onboarding(request: OnboardingRequest):
        """Start a new onboarding session."""
        try:
            session = wf.start_onboarding(request)
            return session.model_dump()
        except Exception as e:
            logger.error("Onboarding start failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/onboarding/{session_id}/collect-info")
    async def collect_info(session_id: str, body: CollectInfoBody):
        """Collect client information."""
        try:
            session = wf.collect_client_info(session_id, body.client_info)
            return session.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/onboarding/{session_id}/approve")
    async def approve_onboarding(session_id: str, body: ApproveBody):
        """HITL approve onboarding."""
        try:
            session = wf.approve_onboarding(session_id, body.reviewer_id)
            return session.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/onboarding/{session_id}")
    async def get_session(session_id: str):
        """Get onboarding session by ID."""
        session = wf.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return session.model_dump()

    return app

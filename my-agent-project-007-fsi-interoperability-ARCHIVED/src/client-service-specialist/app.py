"""
Client Service Specialist — FastAPI REST endpoints.

POST /service/request  — Handle a client service request
GET  /health           — Health check

No cross-module imports. No credentials in code.
"""

import logging

from fastapi import FastAPI, HTTPException

try:
    from .service import ClientServiceEngine
    from .models import ClientServiceRequest
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent
    _s_spec = importlib.util.spec_from_file_location("clientsvc_service_local", _base / "service.py")
    _s_mod = importlib.util.module_from_spec(_s_spec)
    _s_spec.loader.exec_module(_s_mod)
    ClientServiceEngine = _s_mod.ClientServiceEngine
    _m_spec = importlib.util.spec_from_file_location("clientsvc_models_local2", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    ClientServiceRequest = _m_mod.ClientServiceRequest

logger = logging.getLogger("client_service_specialist.app")


def create_app() -> FastAPI:
    """Create the Client Service Specialist FastAPI application."""

    app = FastAPI(
        title="Client Service Specialist",
        description=(
            "Strands/Managed Agents + Haiku specialist for meeting prep, "
            "portfolio review, client summary. <3s response. Per ARCH-09."
        ),
        version="0.1.0",
    )

    engine = ClientServiceEngine()
    app.state.engine = engine

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "client-service-specialist", "version": "0.1.0"}

    @app.post("/service/request")
    async def handle_request(request: ClientServiceRequest):
        """Handle a client service request — routes by request_type."""
        try:
            response = await engine.handle_request(request)
            return response.model_dump()
        except Exception as e:
            logger.error("Service request failed: %s", e)
            raise HTTPException(status_code=500, detail="Service request failed")

    return app

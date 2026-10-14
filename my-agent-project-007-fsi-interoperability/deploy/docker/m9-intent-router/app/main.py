"""
M9 Intent Router -- FastAPI service shim.

Endpoints:
  GET  /health -- liveness
  GET  /ready  -- readiness (env sanity)
  POST /route  -- classify an utterance -> RoutingDecision

Security: no credentials, no cross-module imports (only m9_intent_router,
stdlib, fastapi). Bedrock via IRSA.

See spec .kiro/specs/ops-hardening-wave2-intelligence-layer.md v0.2.0.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from m9_intent_router import (
    SCHEMA_VERSION,
    RouterContext,
    RoutingDecision,
    route as _m9_route,
)
from m9_intent_router.llm_client import FakeLlmClient

app = FastAPI(
    title="M9 Intent Router",
    version=SCHEMA_VERSION,
    docs_url=None,
    redoc_url=None,
)

_READY: dict[str, bool] = {"initialised": False}


class RouteRequest(BaseModel):
    """POST /route body."""

    utterance: str
    context: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": "m9", "version": SCHEMA_VERSION}


@app.get("/ready")
def ready() -> dict[str, Any]:
    if not _READY["initialised"]:
        required = (
            "AWS_REGION",
            "M9_PROVIDER",
            "M9_MODEL_ID",
            "M9_TIMEOUT_MS",
            "M9_CONFIDENCE_HIGH",
            "M9_CONFIDENCE_MED",
        )
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise HTTPException(
                status_code=503, detail={"missing_env": missing}
            )
        _READY["initialised"] = True
    return {"status": "ready", "module": "m9"}


@app.post("/route")
def classify(req: RouteRequest) -> dict[str, Any]:
    """Classify an utterance. Phase 2 uses FakeLlmClient for offline bring-up.

    Production deploy replaces the provider via env + the library's
    BedrockHaikuClient (credentials via IRSA).
    """
    try:
        ctx = RouterContext(**req.context)
        decision: RoutingDecision = _m9_route(
            req.utterance, ctx, _provider=FakeLlmClient(), _config=None
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return decision.model_dump() if hasattr(decision, "model_dump") else dict(decision._asdict())  # type: ignore[attr-defined]

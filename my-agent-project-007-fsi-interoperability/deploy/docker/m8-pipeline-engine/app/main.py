"""
M8 Pipeline Engine -- FastAPI service shim.

Minimum viable HTTP wrapper around the M8 LangGraph library. Lives here
(deploy/docker/...) so the library's public __all__ stays stable and the
shim can evolve with the container image versioning.

Endpoints:
  GET  /health   -- liveness (returns 200 always once the app boots)
  GET  /ready    -- readiness (returns 200 once lazy clients initialised)
  POST /pipelines -- submit a pipeline run; body = PipelineState dict

Security:
  * No credentials in this module.
  * No cross-module imports (only m8_pipeline_engine + stdlib + fastapi).
  * Bedrock access delegated to the library via IRSA-injected creds.

See spec .kiro/specs/ops-hardening-wave2-intelligence-layer.md v0.2.0 R2/R3.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from m8_pipeline_engine import (
    SCHEMA_VERSION,
    PipelineResult,
    run as _m8_run,
)

app = FastAPI(
    title="M8 Pipeline Engine",
    version=SCHEMA_VERSION,
    docs_url=None,   # no public docs
    redoc_url=None,
)

# Ready-state flag. Flipped true after first successful /ready probe.
# Real production wiring would probe Postgres + Vault here; Phase 2 keeps
# the shim minimal.
_READY: dict[str, bool] = {"initialised": False}


class PipelineRequest(BaseModel):
    """POST /pipelines body."""

    initial_state: dict[str, Any]
    thread_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": "m8", "version": SCHEMA_VERSION}


@app.get("/ready")
def ready() -> dict[str, Any]:
    # Lazy init: first probe flips the flag. A real deployment would verify
    # checkpointer DSN resolvable, gateway reachable, audit endpoint up.
    # Phase 2 ships the minimal version; Wave 3 hardens this.
    if not _READY["initialised"]:
        # Env-sanity: required non-secret vars present (from ConfigMap).
        required = (
            "AWS_REGION",
            "M8_MODEL_PROVIDER",
            "M8_MODEL_ID",
            "M8_CHECKPOINTER_BACKEND",
            "M8_GATEWAY_BASE_URL",
            "M8_AUDIT_BASE_URL",
        )
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise HTTPException(
                status_code=503, detail={"missing_env": missing}
            )
        _READY["initialised"] = True
    return {"status": "ready", "module": "m8"}


@app.post("/pipelines")
def submit_pipeline(req: PipelineRequest) -> dict[str, Any]:
    """Submit a pipeline run. Phase 2 uses library defaults (fakes)."""
    try:
        result: PipelineResult = _m8_run(req.initial_state, req.thread_id)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.model_dump() if hasattr(result, "model_dump") else dict(result._asdict())  # type: ignore[attr-defined]

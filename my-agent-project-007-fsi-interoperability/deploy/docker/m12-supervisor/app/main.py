"""
M12 Supervisor -- FastAPI service shim.

Endpoints:
  GET  /health   -- liveness
  GET  /ready    -- readiness (env sanity)
  POST /dispatch -- supervisor dispatch: utterance -> specialist -> result

Security: no credentials, library-level imports of M8+M9 permitted per
spec v0.2.0 §4.8 (M12 is the supervisor glue module). Bedrock via IRSA.
KYC adapter URL via ConfigMap env (R3.21).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from m12_supervisor import (
    SCHEMA_VERSION,
    SupervisorResult,
    dispatch as _m12_dispatch,
)

app = FastAPI(
    title="M12 Supervisor",
    version=SCHEMA_VERSION,
    docs_url=None,
    redoc_url=None,
)

_READY: dict[str, bool] = {"initialised": False}


class DispatchRequest(BaseModel):
    """POST /dispatch body."""

    utterance: str
    aid_claims: dict[str, Any]
    trace_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": "m12", "version": SCHEMA_VERSION}


@app.get("/ready")
def ready() -> dict[str, Any]:
    if not _READY["initialised"]:
        required = (
            "AWS_REGION",
            "M12_MODEL_ID",
            "M12_KYC_ADAPTER_URL",  # R3.21 - URL not secret
            "M12_M9_BASE_URL",
            "M12_M8_BASE_URL",
            "M12_DISPATCH_MODE",
        )
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise HTTPException(
                status_code=503, detail={"missing_env": missing}
            )
        _READY["initialised"] = True
    return {"status": "ready", "module": "m12"}


@app.post("/dispatch")
def dispatch(req: DispatchRequest) -> dict[str, Any]:
    """Supervisor dispatch. Phase 2 uses library fakes for offline bring-up."""
    try:
        result: SupervisorResult = _m12_dispatch(
            req.utterance,
            req.aid_claims,
            req.trace_id,
            _provider=None,
            _config=None,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.model_dump() if hasattr(result, "model_dump") else dict(result._asdict())  # type: ignore[attr-defined]

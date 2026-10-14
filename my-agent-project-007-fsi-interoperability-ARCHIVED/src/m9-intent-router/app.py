"""
M9 FastAPI application — FSI Intent Router endpoints.

Endpoints:
  POST /intent/classify  — classify user input into structured intent
  GET  /intent/taxonomy   — return full taxonomy (debugging/docs)
  GET  /health            — health check
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from models import ClassificationResult, IntentTaxonomy
from router import IntentRouter
from taxonomy import build_taxonomy

logger = logging.getLogger("m9.app")

# ── Shared state ─────────────────────────────────────────────────

_router: IntentRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _router
    _router = IntentRouter()
    logger.info("M9 Intent Router started")
    yield
    if _router is not None:
        await _router.close()
    logger.info("M9 Intent Router stopped")


app = FastAPI(
    title="M9 FSI Intent Router",
    description="Classifies natural language into structured FSI intents",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ────────────────────────────────────


class ClassifyRequest(BaseModel):
    """POST /intent/classify request body."""
    user_input: str = Field(..., min_length=1, max_length=4096)
    aid_claims: dict[str, Any] | None = Field(
        default=None,
        description="AID claims from M1 identity verification",
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    module: str = "m9-intent-router"
    version: str = "1.0.0"


# ── Endpoints ────────────────────────────────────────────────────


@app.post("/intent/classify", response_model=ClassificationResult)
async def classify_intent(request: ClassifyRequest) -> ClassificationResult:
    """Classify user input into a structured FSI intent."""
    if _router is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return await _router.classify_intent(
        user_input=request.user_input,
        aid_claims=request.aid_claims,
    )


@app.get("/intent/taxonomy", response_model=IntentTaxonomy)
async def get_taxonomy() -> IntentTaxonomy:
    """Return the full FSI intent taxonomy (debugging/docs)."""
    return build_taxonomy()


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


# ── v2 endpoint: Strands + Bedrock Haiku (ARCH-10 Decision 1) ────


@app.post("/intent/classify/v2", response_model=ClassificationResult)
async def classify_intent_v2_endpoint(request: ClassifyRequest) -> ClassificationResult:
    """v2 classification: Strands Agent with Bedrock Haiku function-calling.

    Activates only when AWS credentials + strands-agents are available.
    If v2 is unavailable, the endpoint returns a 503 — use v1 instead.
    """
    try:
        from router_v2 import classify_intent_v2
    except Exception as exc:
        logger.warning("v2 router unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="v2 router unavailable (strands-agents or Bedrock not configured)",
        )
    return classify_intent_v2(
        user_input=request.user_input,
        aid_claims=request.aid_claims,
    )


@app.post("/intent/classify-auto", response_model=ClassificationResult)
async def classify_intent_auto(request: ClassifyRequest) -> ClassificationResult:
    """Dispatch to v1 or v2 based on the M9_ROUTER_VERSION env var.

    Defaults to v1 (keyword fast path). Set M9_ROUTER_VERSION=v2 to route
    everything through the Strands agent.
    """
    import os as _os
    version = _os.environ.get("M9_ROUTER_VERSION", "v1")
    if version == "v2":
        try:
            from router_v2 import classify_intent_v2
            return classify_intent_v2(
                user_input=request.user_input,
                aid_claims=request.aid_claims,
            )
        except Exception as exc:
            logger.warning("v2 failed, falling back to v1: %s", exc)
    # v1 fallback
    if _router is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return await _router.classify_intent(
        user_input=request.user_input,
        aid_claims=request.aid_claims,
    )

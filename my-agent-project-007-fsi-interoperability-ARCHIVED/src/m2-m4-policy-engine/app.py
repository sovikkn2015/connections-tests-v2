"""
M2/M4 FastAPI application — Unified Authority + MNPI Policy Engine.

Endpoints:
  POST /policy/authority     — evaluate authority (called by M6)
  POST /policy/mnpi/filter   — filter MNPI fields (called by M6)
  GET  /policy/bundles       — list loaded policy bundles and versions
  GET  /health               — health check (includes OPA connectivity)

All compliance decisions are OPA/Rego ONLY. No LLM. Ever.
FAIL-CLOSED: if OPA unreachable, DENY all requests.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from .models import (
    BundleInfo,
    BundleListResponse,
    HealthResponse,
    MnpiFilterInput,
    MnpiFilterOutput,
    PolicyInput,
    PolicyOutput,
)
from .policy_client import (
    check_opa_health,
    evaluate_authority,
    evaluate_authority_local,
    evaluate_mnpi_filter,
    evaluate_mnpi_filter_local,
)

logger = logging.getLogger(__name__)


def _use_local() -> bool:
    """Check at call time whether to use local evaluator (dev/test)."""
    return os.environ.get("USE_LOCAL_EVALUATOR", "false").lower() == "true"


app = FastAPI(
    title="M2/M4 Policy Engine",
    description=(
        "Unified Authority + MNPI Policy Engine. "
        "OPA/Rego ONLY. No LLM. Fail-closed."
    ),
    version="0.1.0",
)



# ── POST /policy/authority ───────────────────────────────────────


@app.post("/policy/authority", response_model=PolicyOutput)
async def authority_endpoint(policy_input: PolicyInput) -> PolicyOutput:
    """
    Evaluate authority policy: (identity, action, target, context) -> ALLOW/DENY/ESCALATE.
    Called by M6 gateway on every request.
    FAIL-CLOSED: returns DENY if OPA unreachable.
    """
    logger.info(
        "Authority check: action=%s archetype=%s role=%s",
        policy_input.action,
        policy_input.identity.archetype.value,
        policy_input.identity.role.value,
    )

    if _use_local():
        return evaluate_authority_local(policy_input)

    return await evaluate_authority(policy_input)


# ── POST /policy/mnpi/filter ────────────────────────────────────


@app.post("/policy/mnpi/filter", response_model=MnpiFilterOutput)
async def mnpi_filter_endpoint(filter_input: MnpiFilterInput) -> MnpiFilterOutput:
    """
    Filter MNPI fields from data payload based on archetype/role/jurisdiction.
    Called by M6 gateway before data reaches LLM or user.
    FAIL-CLOSED: strips ALL fields if OPA unreachable.
    MNPI filter log is ALWAYS produced (regulatory requirement).
    """
    logger.info(
        "MNPI filter: archetype=%s role=%s fields=%d",
        filter_input.archetype.value,
        filter_input.role.value,
        len(filter_input.data_payload),
    )

    if _use_local():
        return evaluate_mnpi_filter_local(filter_input)

    return await evaluate_mnpi_filter(filter_input)


# ── GET /policy/bundles ──────────────────────────────────────────


@app.get("/policy/bundles", response_model=BundleListResponse)
async def list_bundles() -> BundleListResponse:
    """List loaded OPA policy bundles and their versions."""
    bundles = [
        BundleInfo(
            name="authority",
            version="0.1.0",
            path="opa-bundles/authority/",
            rule_count=5,
            last_updated=datetime.now(timezone.utc),
        ),
        BundleInfo(
            name="mnpi",
            version="0.1.0",
            path="opa-bundles/mnpi/",
            rule_count=6,
            last_updated=datetime.now(timezone.utc),
        ),
    ]
    return BundleListResponse(bundles=bundles)


# ── GET /health ──────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check including OPA connectivity.
    If OPA unreachable, status is 'unhealthy' — fail-closed applies.
    """
    if _use_local():
        return HealthResponse(status="healthy", opa_reachable=True)

    opa_ok = await check_opa_health()
    status = "healthy" if opa_ok else "unhealthy"
    return HealthResponse(status=status, opa_reachable=opa_ok)

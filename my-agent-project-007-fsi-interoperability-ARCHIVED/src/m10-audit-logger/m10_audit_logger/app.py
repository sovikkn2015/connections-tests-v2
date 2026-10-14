"""
M10 FastAPI application — Audit Logger REST endpoints.

Endpoints:
  POST /audit/write  — Write audit entry to all 3 tiers (fail-closed)
  GET  /audit/query   — Query audit entries by trace_id
  GET  /health        — Health check for all 3 tiers

All backends are injected via dependency injection.
Zero credentials in code (Rule 9).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from m10_audit_logger.audit_service import AuditService, AuditWriteError
from m10_audit_logger.models import (
    QueryAuditResponse,
    WriteAuditRequest,
    WriteAuditResponse,
)
from m10_audit_logger.writers import CrmWriter, LangfuseWriter, WormWriter

app = FastAPI(
    title="M10 Audit Logger",
    description=(
        "Three-tier regulatory audit system. "
        "Langfuse + S3 Object Lock WORM + CRM. "
        "Fail-closed. SHA-256 integrity. 6-year retention."
    ),
    version="0.1.0",
)

# ── Singleton service (dev/test: in-memory backends) ─────────────

_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """
    Dependency injection for AuditService.

    Dev/test: in-memory writers (no external dependencies).
    Production: inject real Langfuse/S3/CRM clients via configure().
    """
    global _service
    if _service is None:
        _service = AuditService(
            langfuse_writer=LangfuseWriter(),
            worm_writer=WormWriter(),
            crm_writer=CrmWriter(),
        )
    return _service


def configure(service: AuditService) -> None:
    """Replace the default service with a configured one (production)."""
    global _service
    _service = service


# ── Endpoints ────────────────────────────────────────────────────


@app.post(
    "/audit/write",
    response_model=WriteAuditResponse,
    status_code=201,
    summary="Write audit entry to all 3 tiers",
    responses={
        503: {"description": "Audit write failed (fail-closed)"},
    },
)
async def write_audit(
    request: WriteAuditRequest,
    service: AuditService = Depends(get_audit_service),
) -> WriteAuditResponse:
    """
    Write an audit entry to all three tiers (Langfuse, WORM, CRM).

    FAIL-CLOSED: If any tier write fails, returns 503 and the
    originating request MUST be denied. Entry is sent to DLQ.
    """
    try:
        return await service.write_audit(request)
    except AuditWriteError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "audit_write_failed",
                "message": str(exc),
                "tier_results": [
                    r.model_dump(mode="json") for r in exc.tier_results
                ],
            },
        )


@app.get(
    "/audit/query",
    response_model=QueryAuditResponse,
    summary="Query audit entries by trace_id",
)
async def query_audit(
    trace_id: str,
    service: AuditService = Depends(get_audit_service),
) -> QueryAuditResponse:
    """Query audit entries by distributed trace ID."""
    entries = await service.query_by_trace_id(trace_id)
    return QueryAuditResponse(entries=entries, count=len(entries))


@app.get(
    "/health",
    summary="Health check for all 3 audit tiers",
)
async def health_check(
    service: AuditService = Depends(get_audit_service),
) -> JSONResponse:
    """
    Returns health status of all 3 tiers.
    If any tier is unhealthy, returns 503 (fail-closed — Rule 2).
    """
    status = await service.health_check()
    all_healthy = all(status.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"status": "healthy" if all_healthy else "degraded", "tiers": status},
    )

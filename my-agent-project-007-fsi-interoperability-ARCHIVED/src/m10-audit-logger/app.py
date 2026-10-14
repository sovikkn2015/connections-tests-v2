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

import os

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


def _create_langfuse_writer() -> LangfuseWriter:
    """Create LangfuseWriter with real client if env vars are set."""
    url = os.environ.get("LANGFUSE_URL")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if url and public_key and secret_key:
        try:
            from langfuse import Langfuse

            client = Langfuse(
                host=url,
                public_key=public_key,
                secret_key=secret_key,
            )
            return LangfuseWriter(client=client)
        except ImportError:
            pass
    return LangfuseWriter()


def _create_worm_writer() -> WormWriter:
    """Create WormWriter with a real S3 client when env vars are set.

    Two backend modes supported:

    1. Real AWS S3 (production / live-test): set M10_S3_BUCKET (and optionally
       M10_S3_REGION). Credentials come from the standard AWS credential chain
       (Rule 20 — no secrets in code). No endpoint override.
    2. MinIO (docker-compose local dev): set MINIO_ENDPOINT +
       MINIO_ACCESS_KEY + MINIO_SECRET_KEY.

    Falls back to the in-memory WormWriter when neither is configured.
    """
    aws_bucket = os.environ.get("M10_S3_BUCKET")
    aws_region = os.environ.get("M10_S3_REGION", "us-east-1")
    if aws_bucket:
        try:
            import boto3

            s3_client = boto3.client("s3", region_name=aws_region)
            return WormWriter(s3_client=s3_client, bucket=aws_bucket)
        except ImportError:
            pass

    endpoint = os.environ.get("MINIO_ENDPOINT")
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")
    if endpoint and access_key and secret_key:
        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="us-east-1",
            )
            return WormWriter(s3_client=s3_client)
        except ImportError:
            pass
    return WormWriter()


def _create_crm_writer() -> CrmWriter:
    """Create CrmWriter with httpx client for Salesforce if env vars are set."""
    instance_url = os.environ.get("SF_INSTANCE_URL")
    client_id = os.environ.get("SF_CLIENT_ID")
    client_secret = os.environ.get("SF_CLIENT_SECRET")
    if instance_url and client_id and client_secret:
        try:
            import httpx

            client = httpx.AsyncClient(
                base_url=instance_url,
                headers={"Authorization": f"Bearer {client_id}:{client_secret}"},
            )
            return CrmWriter(client=client)
        except ImportError:
            pass
    return CrmWriter()


def get_audit_service() -> AuditService:
    """
    Dependency injection for AuditService.

    Reads env vars to create real backend clients when available:
      - MINIO_ENDPOINT + MINIO_ACCESS_KEY + MINIO_SECRET_KEY → boto3 S3 for WormWriter
      - LANGFUSE_URL + LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY → Langfuse client
      - SF_INSTANCE_URL + SF_CLIENT_ID + SF_CLIENT_SECRET → httpx for CrmWriter

    Falls back to in-memory writers when env vars are not set or
    libraries are not installed (dev/test behavior preserved).
    """
    global _service
    if _service is None:
        _service = AuditService(
            langfuse_writer=_create_langfuse_writer(),
            worm_writer=_create_worm_writer(),
            crm_writer=_create_crm_writer(),
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

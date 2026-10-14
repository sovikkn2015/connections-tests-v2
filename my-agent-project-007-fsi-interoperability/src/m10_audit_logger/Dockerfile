# syntax=docker/dockerfile:1.6
#
# M10 Audit Logger -- FastAPI REST container.
#
# v0.3.0 ships the `POST /audit` endpoint consumed by M8's
# `M10AuditClient` (see SHARED-WITH-M10 blocker row 18 in
# .kiro/specs/m8-pipeline-engine.md).
#
# Runtime invariants:
# * Non-root UID 1000 (defense-in-depth).
# * Listens on 8443 only. mTLS terminates upstream in the service mesh.
# * Zero credentials baked in; all secrets injected via Vault/Secrets
#   Manager at runtime (Steering Rule 20).
# * No network calls at image-build time.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# `curl` only for HEALTHCHECK; apt cleanup in the same layer.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

# Create a non-privileged runtime user (UID 1000).
RUN groupadd --gid 1000 m10 \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m10

WORKDIR /app

# Pin the minimum dependency set. Real production images will install
# from the project pyproject.toml extras; this is sufficient for the
# Phase-1 in-memory backend shipped with v0.3.0.
RUN pip install --no-cache-dir \
    "fastapi>=0.111,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0"

# Copy only the M10 package + its M3 schema dependency.
# The build-context invariants live in the umbrella Helm chart.
COPY --chown=m10:m10 src/m3_schema_registry /app/m3_schema_registry
COPY --chown=m10:m10 src/m10_audit_logger    /app/m10_audit_logger

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8443/health || exit 1

ENTRYPOINT ["uvicorn", "m10_audit_logger.app:app", \
            "--host", "0.0.0.0", "--port", "8443", "--workers", "2"]

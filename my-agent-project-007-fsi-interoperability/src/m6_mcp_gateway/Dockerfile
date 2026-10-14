# syntax=docker/dockerfile:1.6
#
# M6 Trust-Aware MCP Gateway -- FastAPI REST container (v0.3.0).
#
# Publishes the four routes consumed by the rest of the 007 platform:
#   GET  /health
#   GET  /adapters        (M8 pods hydrate LocalVendorAdapterResolver)
#   GET  /gateway/reasons (peer modules verify reason-vocab alignment)
#   POST /gateway/call    (every MCP call in the platform lands here)
#
# Runtime invariants:
# * Non-root UID 1000 (defense-in-depth).
# * Listens on 8443 only. mTLS terminates upstream in the service mesh
#   (Steering Rule 21) -- this container does NOT authenticate callers.
# * Zero credentials baked in; all secrets injected via Vault / AWS
#   Secrets Manager at runtime (Steering Rule 20).
# * No network calls at image-build time.
# * No stdlib `logging` -- access lines are emitted via structured
#   stdout JSON from the FastAPI middleware.

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

# Non-privileged runtime user (UID 1000).
RUN groupadd --gid 1000 m6 \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m6

WORKDIR /app

# Pin the minimum dependency set. Phase-2 images will install from the
# project pyproject.toml extras; this is sufficient for v0.3.0.
RUN pip install --no-cache-dir \
    "fastapi>=0.111,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0" \
    "httpx>=0.27,<1.0" \
    "pyjwt>=2.8,<3.0"

# M6 depends on the in-process trust-layer modules via Python imports;
# the umbrella Helm chart arranges the build context so these paths
# resolve. Each COPY is chowned to the runtime UID.
COPY --chown=m6:m6 src/m1_identity            /app/m1_identity
COPY --chown=m6:m6 src/m2_m4_policy_engine    /app/m2_m4_policy_engine
COPY --chown=m6:m6 src/m3_schema_registry     /app/m3_schema_registry
COPY --chown=m6:m6 src/m5_config_loader       /app/m5_config_loader
COPY --chown=m6:m6 src/m10_audit_logger       /app/m10_audit_logger
COPY --chown=m6:m6 src/compliance             /app/compliance
COPY --chown=m6:m6 src/m6_mcp_gateway         /app/m6_mcp_gateway

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8443/health || exit 1

ENTRYPOINT ["uvicorn", "m6_mcp_gateway.app:app", \
            "--host", "0.0.0.0", "--port", "8443", "--workers", "2"]

# syntax=docker/dockerfile:1.7
#
# M6 Trust-Aware MCP Gateway -- FastAPI REST container (Ops Hardening Wave 1).
#
# NOTE: ``src/m6_mcp_gateway/Dockerfile`` remains authoritative for local
# laptop dev (single-stage, listens on 8443 directly). This file is the
# canonical PROD Dockerfile used by docker-compose and Helm. Key
# differences:
#
# * Multi-stage build (builder + runtime).
# * Single listener on port 8080 (Service maps 8443 -> 8080).
# * Explicit standardised mount paths for mTLS + Vault token.
# * OCI image-spec labels at the runtime layer.
#
# Build context:    my-agent-project-007-fsi-interoperability/
# Image target:     007-fsi/m6-mcp-gateway
# Port contract:    single uvicorn listener on 8080
# User:             numeric UID 1000, non-root
# mTLS mount:       /etc/007/mtls/{tls.crt,tls.key,ca.crt}
# Vault token:      /var/run/secrets/vault/token
# Healthcheck:      GET http://localhost:8080/health

# ---------------------------------------------------------------------------
# Stage 1 -- builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /wheels

RUN pip install --no-cache-dir \
      "fastapi>=0.111,<1.0" \
      "uvicorn[standard]>=0.30,<1.0" \
      "pydantic>=2.0,<3.0" \
      "httpx>=0.27,<1.0" \
      "pyjwt>=2.8,<3.0" \
      "cryptography>=42,<46"

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="007-fsi/m6-mcp-gateway" \
      org.opencontainers.image.version="0.3.0" \
      org.opencontainers.image.source="https://example.invalid/007-fsi" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Project 007"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m6 \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m6 \
 && mkdir -p /etc/007/mtls /var/run/secrets/vault \
 && chown -R 1000:1000 /etc/007 /var/run/secrets/vault \
 && chmod 0755 /etc/007 /etc/007/mtls /var/run/secrets/vault

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# M6 depends on the in-process trust-layer modules via Python imports.
COPY --chown=1000:1000 src/m1_identity            /app/m1_identity
COPY --chown=1000:1000 src/m2_m4_policy_engine    /app/m2_m4_policy_engine
COPY --chown=1000:1000 src/m3_schema_registry     /app/m3_schema_registry
COPY --chown=1000:1000 src/m5_config_loader       /app/m5_config_loader
COPY --chown=1000:1000 src/m10_audit_logger       /app/m10_audit_logger
COPY --chown=1000:1000 src/compliance             /app/compliance
COPY --chown=1000:1000 src/m6_mcp_gateway         /app/m6_mcp_gateway

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["uvicorn", "m6_mcp_gateway.app:app", \
            "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]

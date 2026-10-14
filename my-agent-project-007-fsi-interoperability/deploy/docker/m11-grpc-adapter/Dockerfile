# syntax=docker/dockerfile:1.7
#
# M11 gRPC Adapter -- ICE Data Services (Python 3.12, FastAPI MCP server).
#
# Build context:    my-agent-project-007-fsi-interoperability/
# Image target:     007-fsi/m11-grpc-adapter
# Port contract:    uvicorn listener on 8080 (Service maps 8443 -> 8080)
# User:             numeric UID 1000, non-root
# mTLS mount:       /etc/007/mtls/{tls.crt,tls.key,ca.crt} (0400 for key)
# Vault token:      /var/run/secrets/vault/token
# Healthcheck:      GET http://localhost:8080/ returns 200 when healthy
#                   OR ICE_ENABLED=false (graceful-disabled mode).
#
# Steering rules:
# * Rule 10 -- polyglot M11; this is the Python half (gRPC).
# * Rule 20 -- zero credentials; bearer token + mTLS key/cert/CA via Vault paths.
# * Rule 32 -- inputs validated via pydantic (extra="forbid").
# * Rule 33 -- no cross-module imports; audit via stdout -> M10 sidecar.

# ---------------------------------------------------------------------------
# Stage 1 -- builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /wheels

# grpcio wheel is pinned; grpcio-tools is for proto regeneration (not shipped
# at runtime but needed in builder for any CI-time stub gen).
RUN pip install --no-cache-dir \
      "fastapi>=0.111,<1.0" \
      "uvicorn[standard]>=0.30,<1.0" \
      "pydantic>=2.0,<3.0" \
      "structlog>=24.1,<26.0" \
      "typing-extensions>=4.10,<5.0" \
      "grpcio>=1.63,<2.0" \
      "protobuf>=5.26,<7.0"

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="007-fsi/m11-grpc-adapter" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://example.invalid/007-fsi" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Project 007"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ICE_ENABLED=false

RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m11grpc \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m11grpc \
 && mkdir -p /etc/007/mtls /var/run/secrets/vault /app/fixtures/ice \
 && chown -R 1000:1000 /etc/007 /var/run/secrets/vault /app \
 && chmod 0755 /etc/007 /etc/007/mtls /var/run/secrets/vault

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY --chown=1000:1000 src/m11_python_adapters_shared /app/m11_python_adapters_shared
COPY --chown=1000:1000 src/m11_grpc_adapters /app/m11_grpc_adapters

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8080/ || exit 1

ENTRYPOINT ["python", "-m", "m11_grpc_adapters.ice_data"]

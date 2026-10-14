# syntax=docker/dockerfile:1.7
#
# M13 FIX Bridge -- Stateful FIX 4.4 TCP sessions exposed as MCP tools.
#
# Build context:    my-agent-project-007-fsi-interoperability/
# Image target:     007-fsi/m13-fix-bridge
# Port contract:    uvicorn listener on 8080 (Service maps 8443 -> 8080)
# User:             numeric UID 1000, non-root
# PV:               /var/lib/m13 (seqnums + kill-switch state) -- StatefulSet PVC
# mTLS mount:       /etc/007/mtls/{tls.crt,tls.key,ca.crt} (0400 for key)
# Vault token:      /var/run/secrets/vault/token
# Healthcheck:      GET http://localhost:8080/ returns 200 when healthy
#                   OR FIX_ENABLED=false (graceful-disabled mode).
#
# Steering rules:
# * Rule 11 -- M13 is SEPARATE from M11; stateful, StatefulSet + PV.
# * Rule 20 -- zero credentials; everything via Vault paths.
# * Rule 32 -- inputs validated via pydantic (extra="forbid", strict=True).
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

# simplefix is the FIX 4.4 message builder. Pinned to the 1.x line.
# pyjwt[crypto] is reserved for the RSA AID-verify mode (Spec §R13.5);
# HMAC mode uses the stdlib implementation.
RUN pip install --no-cache-dir \
      "fastapi>=0.111,<1.0" \
      "uvicorn[standard]>=0.30,<1.0" \
      "pydantic>=2.0,<3.0" \
      "pyyaml>=6.0,<7.0" \
      "structlog>=24.1,<26.0" \
      "typing-extensions>=4.10,<5.0" \
      "simplefix>=1.0.17,<2.0" \
      "pyjwt[crypto]>=2.8.0,<3.0"

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="007-fsi/m13-fix-bridge" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://example.invalid/007-fsi" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Project 007"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FIX_ENABLED=false

RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m13fix \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m13fix \
 && mkdir -p /etc/007/mtls /var/run/secrets/vault /app /var/lib/m13 \
 && chown -R 1000:1000 /etc/007 /var/run/secrets/vault /app /var/lib/m13 \
 && chmod 0755 /etc/007 /etc/007/mtls /var/run/secrets/vault /var/lib/m13

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY --chown=1000:1000 src/m13_fix_bridge /app/m13_fix_bridge

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8080

# Persistent seqnums + kill-switch state live here. StatefulSet PVC binds.
VOLUME /var/lib/m13

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8080/ || exit 1

ENTRYPOINT ["python", "-m", "m13_fix_bridge"]

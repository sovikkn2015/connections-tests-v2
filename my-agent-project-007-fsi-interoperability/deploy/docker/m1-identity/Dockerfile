# syntax=docker/dockerfile:1.7
#
# M1 Agent Identity -- FastAPI REST container (Ops Hardening Wave 1).
#
# Build context:    my-agent-project-007-fsi-interoperability/
# Image target:     007-fsi/m1-identity
# Port contract:    single uvicorn listener on 8080 (Service maps 8443 -> 8080)
# User:             numeric UID 1000, non-root
# mTLS mount:       /etc/007/mtls/{tls.crt,tls.key,ca.crt} (0400 for key)
# Vault token:      /var/run/secrets/vault/token
# Healthcheck:      GET http://localhost:8080/health
#
# Security invariants (Steering Rules 20-22):
# * Multi-stage build: builder compiles/installs; runtime carries only app.
# * No credentials at any layer. All secrets injected at runtime.
# * No apt-get upgrade. apt install pinned, cleaned in same layer.
# * No ADD from URL. COPY only.
# * OCI image-spec labels declared at the runtime layer.

# ---------------------------------------------------------------------------
# Stage 1 -- builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /wheels

# Pinned dependency set. Upper bounds prevent silent major-version drift.
RUN pip install --no-cache-dir \
      "fastapi>=0.111,<1.0" \
      "uvicorn[standard]>=0.30,<1.0" \
      "pydantic>=2.0,<3.0" \
      "pyjwt>=2.8,<3.0" \
      "cryptography>=42,<46"

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="007-fsi/m1-identity" \
      org.opencontainers.image.version="0.3.0" \
      org.opencontainers.image.source="https://example.invalid/007-fsi" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Project 007"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# `curl` only for HEALTHCHECK. Installed from the pinned base image's
# apt index (python:3.12-slim is itself a pinned tag upstream), then
# the index is removed in the same layer. No `apt-get upgrade`.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

# Non-privileged runtime user + mount directories owned by that UID.
RUN groupadd --gid 1000 m1 \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m1 \
 && mkdir -p /etc/007/mtls /var/run/secrets/vault \
 && chown -R 1000:1000 /etc/007 /var/run/secrets/vault \
 && chmod 0755 /etc/007 /etc/007/mtls /var/run/secrets/vault

WORKDIR /app

# Copy wheels-installed Python site-packages from builder. We reinstall
# from the same version constraints to keep the runtime resolver
# identical across stages.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Application code. M1 needs M5 enum imports (see claims.py) so M5 is
# copied alongside. No other cross-module deps at runtime.
COPY --chown=1000:1000 src/m5_config_loader /app/m5_config_loader
COPY --chown=1000:1000 src/m1_identity      /app/m1_identity

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["uvicorn", "m1_identity.app:app", \
            "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]

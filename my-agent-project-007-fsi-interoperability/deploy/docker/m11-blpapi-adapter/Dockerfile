# syntax=docker/dockerfile:1.7
#
# M11 BLPAPI Adapter -- Bloomberg refdata (Python 3.12, FastAPI MCP server).
#
# Build context:    my-agent-project-007-fsi-interoperability/
# Image target:     007-fsi/m11-blpapi-adapter
# Port contract:    uvicorn listener on 8080 (Service maps 8443 -> 8080)
# User:             numeric UID 1000, non-root
# mTLS mount:       /etc/007/mtls/{tls.crt,tls.key,ca.crt} (0400 for key)
# Vault token:      /var/run/secrets/vault/token
# Healthcheck:      GET http://localhost:8080/ returns 200 when authorized
#                   OR when BLPAPI_ENABLED=false (graceful-disabled mode).
#
# Steering rules:
# * Rule 10 -- polyglot M11; this is the Python half.
# * Rule 20 -- zero credentials; UUID + serial via Vault paths.
# * Rule 32 -- inputs validated via pydantic (extra="forbid").
# * Rule 33 -- no cross-module imports; audit via stdout -> M10 sidecar.
#
# BLPAPI wheel:
# * The `blpapi` Python module is proprietary. Operators with a Bloomberg
#   Terminal Data License supply the wheel at build time via
#   `--build-arg BLPAPI_WHEEL_PATH=./blpapi-3.24.6-cp312-cp312-linux_x86_64.whl`.
# * Without the build arg, the image ships in pure-fake mode: the FakeBlpapiClient
#   answers every tool call from fixtures, and when BLPAPI_ENABLED=true is set at
#   runtime without the wheel installed, the adapter fails-fast on startup.

ARG BLPAPI_WHEEL_PATH=""

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
      "structlog>=24.1,<26.0" \
      "typing-extensions>=4.10,<5.0"

# Optional BLPAPI wheel -- copied in only when BLPAPI_WHEEL_PATH is supplied.
# We copy the marker file `.dockerignore` instead of failing when empty,
# so the pure-fake build path stays valid.
ARG BLPAPI_WHEEL_PATH
COPY ${BLPAPI_WHEEL_PATH:-deploy/docker/m11-blpapi-adapter/Dockerfile} /tmp/blpapi_wheel_maybe
RUN if [ -n "${BLPAPI_WHEEL_PATH}" ] && [ -f /tmp/blpapi_wheel_maybe ] && \
        echo "/tmp/blpapi_wheel_maybe" | grep -q '\.whl$'; then \
      pip install --no-cache-dir /tmp/blpapi_wheel_maybe ; \
    else \
      echo "no blpapi wheel supplied; image ships in pure-fake mode" ; \
    fi

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="007-fsi/m11-blpapi-adapter" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://example.invalid/007-fsi" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Project 007"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BLPAPI_ENABLED=false

# curl only for HEALTHCHECK. Pinned base image; no apt-get upgrade.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

# Non-privileged runtime user + mount directories owned by that UID.
RUN groupadd --gid 1000 m11blp \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m11blp \
 && mkdir -p /etc/007/mtls /var/run/secrets/vault /app/fixtures/bloomberg \
 && chown -R 1000:1000 /etc/007 /var/run/secrets/vault /app \
 && chmod 0755 /etc/007 /etc/007/mtls /var/run/secrets/vault

WORKDIR /app

# Copy wheels-installed Python site-packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Application code. Shared infra + the adapter itself. No M6/M10 imports
# allowed here (verified by module-boundary test).
COPY --chown=1000:1000 src/m11_python_adapters_shared /app/m11_python_adapters_shared
COPY --chown=1000:1000 src/m11_blpapi_adapters /app/m11_blpapi_adapters
COPY --chown=1000:1000 tests/fixtures/bloomberg /app/fixtures/bloomberg

ENV PYTHONPATH=/app

USER 1000

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8080/ || exit 1

ENTRYPOINT ["python", "-m", "m11_blpapi_adapters.bloomberg_refdata"]

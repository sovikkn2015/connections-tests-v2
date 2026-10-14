# syntax=docker/dockerfile:1.6
#
# M9 Intent Router -- FastAPI service container.
#
# Wraps the M9 LLM function-calling classifier (Haiku) behind a thin
# HTTP API. Spec: .kiro/specs/ops-hardening-wave2-intelligence-layer.md
# v0.2.0 (R2, R3.12-R3.18).
#
# Runtime invariants: non-root UID 1000, port 8443, IRSA for Bedrock,
# zero credentials baked in.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m9 \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m9

WORKDIR /app

# boto3 = Bedrock client; no langgraph needed (M9 is stateless).
RUN pip install --no-cache-dir \
    "fastapi>=0.111,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0" \
    "boto3>=1.34,<2.0"

COPY --chown=m9:m9 src/m3_schema_registry         /app/m3_schema_registry
COPY --chown=m9:m9 src/m9_intent_router           /app/m9_intent_router
COPY --chown=m9:m9 deploy/docker/m9-intent-router/app  /app/service

ENV PYTHONPATH=/app

ENV AWS_REGION=us-east-1 \
    M9_PROVIDER=bedrock \
    M9_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0 \
    M9_TIMEOUT_MS=1500 \
    M9_FALLBACK_ENABLED=true \
    M9_CONFIDENCE_HIGH=0.95 \
    M9_CONFIDENCE_MED=0.80 \
    M9_TENANT_HMAC_KEY_VAULT_PATH=secret/data/m9/tenants/PLACEHOLDER/hmac_key

USER 1000

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:8443/health || exit 1

ENTRYPOINT ["uvicorn", "service.main:app", \
            "--host", "0.0.0.0", "--port", "8443", "--workers", "4"]

# syntax=docker/dockerfile:1.6
#
# M12 Supervisor -- FastAPI service container.
#
# Supervisor glue: channel -> M9 intent router -> M8 research pipeline
# -> M10 audit. Phase 2 lighthouse uses in-process library imports;
# Phase 3 flips M12_DISPATCH_MODE=remote for HTTP fan-out.
#
# Spec: .kiro/specs/ops-hardening-wave2-intelligence-layer.md v0.2.0
# (R2, R3.19-R3.25).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m12 \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m12

WORKDIR /app

# langgraph pulled in because M12 imports M8 library in Phase 2 (see §4.8).
# boto3 for Bedrock via IRSA.
RUN pip install --no-cache-dir \
    "fastapi>=0.111,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0" \
    "langgraph>=0.2,<0.3" \
    "boto3>=1.34,<2.0"

# M12 bundles its specialist dependencies (M8 + M9) for Phase 2 lighthouse
# in-process dispatch. Phase 3 container strips these once dispatch_mode=remote
# is the only supported path.
COPY --chown=m12:m12 src/m3_schema_registry        /app/m3_schema_registry
COPY --chown=m12:m12 src/compliance                /app/compliance
COPY --chown=m12:m12 src/m8_pipeline_engine        /app/m8_pipeline_engine
COPY --chown=m12:m12 src/m9_intent_router          /app/m9_intent_router
COPY --chown=m12:m12 src/m12_supervisor            /app/m12_supervisor
COPY --chown=m12:m12 deploy/docker/m12-supervisor/app  /app/service

ENV PYTHONPATH=/app

ENV AWS_REGION=us-east-1 \
    M12_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0 \
    M12_KYC_ADAPTER_URL=https://m11-kyc.internal:8443 \
    M12_HITL_HMAC_KEY_VAULT_PATH=secret/data/m12/hitl_hmac_key \
    M12_M9_BASE_URL=https://m9-intent-router.internal:8443 \
    M12_M8_BASE_URL=https://m8-pipeline-engine.internal:8443 \
    M12_DISPATCH_MODE=local

USER 1000

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -sf http://localhost:8443/health || exit 1

ENTRYPOINT ["uvicorn", "service.main:app", \
            "--host", "0.0.0.0", "--port", "8443", "--workers", "2"]

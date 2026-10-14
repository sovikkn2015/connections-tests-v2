# syntax=docker/dockerfile:1.6
#
# M8 Pipeline Engine -- FastAPI service container.
#
# Wraps the LangGraph 23-stage research pipeline behind a thin HTTP API.
# Matches the spec at .kiro/specs/ops-hardening-wave2-intelligence-layer.md
# v0.2.0 (Step 5 build).
#
# Runtime invariants (see spec R2):
#   * Non-root UID 1000.
#   * Listens on 8443. mTLS terminates at service mesh; plaintext inside pod.
#   * Zero credentials baked in -- secrets injected via Vault/IRSA at runtime.
#   * Bedrock access via IRSA (pod ServiceAccount role annotation).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl for HEALTHCHECK only; clean apt lists in same layer.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 m8 \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /sbin/nologin m8

WORKDIR /app

# Pinned service dependencies (R2.10, R2.11).
# psycopg[binary] = Postgres checkpointer backend (R3.4/R3.5).
# langgraph        = pipeline orchestration (Rule 1).
# boto3            = Bedrock client behind LLMProvider abstraction (Rule 9).
RUN pip install --no-cache-dir \
    "fastapi>=0.111,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0" \
    "langgraph>=0.2,<0.3" \
    "psycopg[binary]>=3.1,<4.0" \
    "boto3>=1.34,<2.0"

# Copy library + service shim. M3 schemas + compliance sub-modules are M8 deps.
COPY --chown=m8:m8 src/m3_schema_registry       /app/m3_schema_registry
COPY --chown=m8:m8 src/compliance               /app/compliance
COPY --chown=m8:m8 src/m8_pipeline_engine       /app/m8_pipeline_engine
COPY --chown=m8:m8 deploy/docker/m8-pipeline-engine/app  /app/service

ENV PYTHONPATH=/app

# Non-secret runtime defaults (R3.1-R3.11). No credentials, only Vault paths.
ENV AWS_REGION=us-east-1 \
    M8_MODEL_PROVIDER=bedrock \
    M8_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0 \
    M8_CHECKPOINTER_BACKEND=postgres \
    M8_CHECKPOINTER_DSN_VAULT_PATH=secret/data/m8/checkpointer_dsn \
    M8_HITL_HMAC_KEY_VAULT_PATH=secret/data/m8/hitl_hmac_key \
    M8_GATEWAY_BASE_URL=https://m6-gateway.internal:8443 \
    M8_AUDIT_BASE_URL=https://m10-audit.internal:8443 \
    M8_HITL_TIMEOUT_SECONDS=14400 \
    M8_MAX_WALL_CLOCK_SECONDS=1200 \
    M8_ALERT_WALL_CLOCK_SECONDS=900

USER 1000

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -sf http://localhost:8443/health || exit 1

ENTRYPOINT ["uvicorn", "service.main:app", \
            "--host", "0.0.0.0", "--port", "8443", "--workers", "2"]

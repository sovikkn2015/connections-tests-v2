"""
M8 Pipeline Engine -- Checkpointer factory.

R3: PostgreSQL default, DynamoDB reserved (Phase 3 stub), InMemorySaver for
tests. DSN resolved from Vault at process startup.

boto3 allowed here for AWS Secrets Manager DSN resolution (AC13.3).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]


@lru_cache(maxsize=4)
def _resolve_dsn(vault_path: str) -> str:
    """Fetch DSN from AWS Secrets Manager (AC3.2, AC14.3)."""
    if not vault_path:
        raise RuntimeError("m8_checkpointer_dsn_unresolved")
    if boto3 is None:
        raise RuntimeError("m8_checkpointer_dsn_unresolved")
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=vault_path)
        dsn = response.get("SecretString") or ""
        if isinstance(dsn, bytes):
            dsn = dsn.decode("utf-8")
        if not dsn:
            raise RuntimeError("m8_checkpointer_dsn_unresolved")
        return dsn
    except Exception as exc:
        raise RuntimeError(f"m8_checkpointer_dsn_unresolved: {exc!r}")


class DynamoDbSaver:
    """Reserved Phase 3 DynamoDB checkpointer (AC3.9)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Phase 3")


class PostgresSaver:
    """Wrapper around ``langgraph.checkpoint.postgres.PostgresSaver``."""

    @classmethod
    def from_conn_string(cls, dsn: str) -> Any:
        try:
            from langgraph.checkpoint.postgres import (
                PostgresSaver as _PGSaver,
            )
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"m8_checkpointer_unavailable: {exc!r}")
        return _PGSaver.from_conn_string(dsn)


def build_checkpointer(config: Any) -> Any:
    """Construct a BaseCheckpointSaver from PipelineConfig (AC3.1)."""
    backend = getattr(config, "checkpointer_backend", "postgres")
    if backend == "postgres":
        dsn_path = getattr(config, "checkpointer_dsn_vault_path", "")
        dsn = _resolve_dsn(dsn_path)
        return PostgresSaver.from_conn_string(dsn)
    if backend == "dynamodb":
        return DynamoDbSaver()
    if backend == "memory":
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
    raise ValueError(f"unknown_checkpointer_backend: {backend!r}")


__all__ = [
    "build_checkpointer",
    "PostgresSaver",
    "DynamoDbSaver",
]

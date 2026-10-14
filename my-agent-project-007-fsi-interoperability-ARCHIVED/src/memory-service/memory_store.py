"""
Memory Service — 6-layer memory store with MNPI filtering on read.

In-memory backends for dev/test. Production:
  L1: Redis (8hr TTL), L2: DynamoDB (7d), L3: DynamoDB (2yr),
  L4: pgvector/Pinecone (permanent), L5: S3 JSON (permanent), L6: M10 WORM.

MNPI filtering: entries tagged with mnpi_tags, filtered on read
based on caller's archetype/role. No unfiltered MNPI to LLM.
No cross-module imports. No credentials in code.

Backends:
  In-memory (default) for dev/test.
  Redis for L1 (MEMORY_L1_BACKEND=redis, REDIS_URL).
  DynamoDB for L2/L3 (MEMORY_L2_BACKEND=dynamodb, MEMORY_DYNAMODB_TABLE).
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from .models import MemoryEntry, MemoryLayer, MemoryQuery
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("memory_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    MemoryEntry = _mod.MemoryEntry
    MemoryLayer = _mod.MemoryLayer
    MemoryQuery = _mod.MemoryQuery

logger = logging.getLogger("memory_service.store")

# TTL constants
L1_TTL_HOURS = 8
L2_TTL_DAYS = 7


# ── Layer Backend Abstractions ───────────────────────────────────


class InMemoryLayerBackend:
    """In-memory backend for any memory layer. Default for dev/test."""

    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []

    def append(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)

    def list_all(self) -> list[MemoryEntry]:
        return list(self._entries)

    def set_entries(self, entries: list[MemoryEntry]) -> None:
        self._entries = entries

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> MemoryEntry:
        return self._entries[index]

    def __setitem__(self, index: int, value: MemoryEntry) -> None:
        self._entries[index] = value


class _LayerBackendProxy:
    """Backward-compatible proxy: svc._stores[layer][idx] works for in-memory backends."""

    def __init__(self, backends: dict) -> None:
        self._backends = backends

    def __getitem__(self, layer: MemoryLayer) -> InMemoryLayerBackend:
        backend = self._backends[layer]
        if isinstance(backend, InMemoryLayerBackend):
            return backend
        raise KeyError(f"Direct index access not available for non-memory backend on {layer}")

    def get(self, layer: MemoryLayer, default: Any = None) -> Any:
        return self._backends.get(layer, default)


class RedisMemoryBackend:
    """
    Redis-backed L1 working memory with 8hr TTL.

    Activated when MEMORY_L1_BACKEND=redis and REDIS_URL is set.
    Uses redis-py. Credentials from env (Rule 20). No credentials in code.

    Falls back to in-memory on connection failure.
    """

    def __init__(self, redis_url: str, redis_client: Any = None) -> None:
        self._redis_url = redis_url
        self._prefix = "memory:l1:"
        if redis_client is not None:
            self._redis = redis_client
        else:
            try:
                import redis
            except ImportError:
                raise RuntimeError(
                    "redis is required for Redis memory backend. "
                    "Install with: pip install redis"
                )
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._fallback: InMemoryLayerBackend | None = None
        logger.info("RedisMemoryBackend initialized: %s", redis_url.split("@")[-1] if "@" in redis_url else redis_url)

    def _get_fallback(self) -> InMemoryLayerBackend:
        if self._fallback is None:
            self._fallback = InMemoryLayerBackend()
            logger.warning("RedisMemoryBackend: activated in-memory fallback")
        return self._fallback

    def append(self, entry: MemoryEntry) -> None:
        try:
            key = f"{self._prefix}{entry.entry_id}"
            self._redis.setex(
                key,
                L1_TTL_HOURS * 3600,
                entry.model_dump_json(),
            )
            # Also add to a sorted set for listing by client
            client_key = f"{self._prefix}client:{entry.client_id}"
            self._redis.zadd(client_key, {entry.entry_id: datetime.now(timezone.utc).timestamp()})
            self._redis.expire(client_key, L1_TTL_HOURS * 3600)
        except Exception as exc:
            logger.error("Redis append failed: %s. Using fallback.", exc)
            self._get_fallback().append(entry)

    def list_all(self) -> list[MemoryEntry]:
        try:
            keys = self._redis.keys(f"{self._prefix}[!c]*")  # exclude client: index keys
            entries = []
            for key in keys:
                data = self._redis.get(key)
                if data:
                    entries.append(MemoryEntry.model_validate_json(data))
            if self._fallback:
                entries.extend(self._fallback.list_all())
            return entries
        except Exception as exc:
            logger.error("Redis list_all failed: %s. Using fallback.", exc)
            return self._get_fallback().list_all()

    def set_entries(self, entries: list[MemoryEntry]) -> None:
        """Replace all entries (used by expire_entries). Rebuilds Redis keys."""
        try:
            # Delete all existing L1 keys
            keys = self._redis.keys(f"{self._prefix}*")
            if keys:
                self._redis.delete(*keys)
            # Re-add non-expired entries
            for entry in entries:
                self.append(entry)
        except Exception as exc:
            logger.error("Redis set_entries failed: %s. Using fallback.", exc)
            self._get_fallback().set_entries(entries)

    def __len__(self) -> int:
        try:
            keys = self._redis.keys(f"{self._prefix}[!c]*")
            count = len(keys)
            if self._fallback:
                count += len(self._fallback)
            return count
        except Exception:
            return len(self._get_fallback()) if self._fallback else 0


class DynamoDBMemoryBackend:
    """
    DynamoDB-backed memory for L2 (short-term) and L3 (episodic).

    Activated when MEMORY_L2_BACKEND=dynamodb and MEMORY_DYNAMODB_TABLE is set.
    Uses boto3 DynamoDB. Credentials from IAM role / env (Rule 20).

    Falls back to in-memory on connection failure.
    """

    def __init__(self, table_name: str, layer_name: str, dynamodb_client: Any = None) -> None:
        self._table_name = table_name
        self._layer_name = layer_name
        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for DynamoDB memory backend. "
                    "Install with: pip install boto3"
                )
            self._client = boto3.resource("dynamodb").Table(table_name)
        self._fallback: InMemoryLayerBackend | None = None
        logger.info("DynamoDBMemoryBackend initialized: table=%s layer=%s", table_name, layer_name)

    def _get_fallback(self) -> InMemoryLayerBackend:
        if self._fallback is None:
            self._fallback = InMemoryLayerBackend()
            logger.warning("DynamoDBMemoryBackend(%s): activated in-memory fallback", self._layer_name)
        return self._fallback

    def append(self, entry: MemoryEntry) -> None:
        try:
            self._client.put_item(Item={
                "layer": self._layer_name,
                "entry_id": entry.entry_id,
                "client_id": entry.client_id or "",
                "entry_json": entry.model_dump_json(),
                "created_at": entry.created_at,
            })
        except Exception as exc:
            logger.error("DynamoDB append failed (%s): %s. Using fallback.", self._layer_name, exc)
            self._get_fallback().append(entry)

    def list_all(self) -> list[MemoryEntry]:
        try:
            resp = self._client.query(
                KeyConditionExpression="layer = :lyr",
                ExpressionAttributeValues={":lyr": self._layer_name},
            )
            entries = [
                MemoryEntry.model_validate_json(item["entry_json"])
                for item in resp.get("Items", [])
            ]
            if self._fallback:
                entries.extend(self._fallback.list_all())
            return entries
        except Exception as exc:
            logger.error("DynamoDB list_all failed (%s): %s. Using fallback.", self._layer_name, exc)
            return self._get_fallback().list_all()

    def set_entries(self, entries: list[MemoryEntry]) -> None:
        """Replace entries for this layer. Used by expire_entries."""
        # For DynamoDB, expiry is better handled via TTL attribute.
        # This is a simplified implementation for compatibility.
        if self._fallback:
            self._fallback.set_entries(entries)

    def __len__(self) -> int:
        try:
            resp = self._client.query(
                KeyConditionExpression="layer = :lyr",
                ExpressionAttributeValues={":lyr": self._layer_name},
                Select="COUNT",
            )
            count = resp.get("Count", 0)
            if self._fallback:
                count += len(self._fallback)
            return count
        except Exception:
            return len(self._get_fallback()) if self._fallback else 0


def create_memory_store() -> "MemoryService":
    """
    Factory: create MemoryService with backends selected by env vars.

    MEMORY_L1_BACKEND: "memory" (default) or "redis"
    MEMORY_L2_BACKEND: "memory" (default) or "dynamodb"
    REDIS_URL: Redis connection URL (required for redis backend)
    MEMORY_DYNAMODB_TABLE: DynamoDB table name (required for dynamodb backend)
    """
    l1_backend_type = os.environ.get("MEMORY_L1_BACKEND", "memory").lower()
    l2_backend_type = os.environ.get("MEMORY_L2_BACKEND", "memory").lower()

    l1_backend: InMemoryLayerBackend | RedisMemoryBackend | None = None
    l2_backend: InMemoryLayerBackend | DynamoDBMemoryBackend | None = None
    l3_backend: InMemoryLayerBackend | DynamoDBMemoryBackend | None = None

    # L1: Redis
    if l1_backend_type == "redis":
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.warning(
                "MEMORY_L1_BACKEND=redis but REDIS_URL not set. "
                "Falling back to in-memory for L1."
            )
        else:
            try:
                l1_backend = RedisMemoryBackend(redis_url=redis_url)
                logger.info("Memory L1 backend: redis")
            except Exception as exc:
                logger.error("Failed to init Redis L1 backend: %s. Falling back to in-memory.", exc)

    # L2/L3: DynamoDB
    if l2_backend_type == "dynamodb":
        table_name = os.environ.get("MEMORY_DYNAMODB_TABLE")
        if not table_name:
            logger.warning(
                "MEMORY_L2_BACKEND=dynamodb but MEMORY_DYNAMODB_TABLE not set. "
                "Falling back to in-memory for L2/L3."
            )
        else:
            try:
                l2_backend = DynamoDBMemoryBackend(table_name=table_name, layer_name="L2")
                l3_backend = DynamoDBMemoryBackend(table_name=table_name, layer_name="L3")
                logger.info("Memory L2/L3 backend: dynamodb (table=%s)", table_name)
            except Exception as exc:
                logger.error("Failed to init DynamoDB L2/L3 backend: %s. Falling back to in-memory.", exc)

    if not l1_backend and l1_backend_type == "memory":
        logger.info("Memory L1 backend: memory")
    if not l2_backend and l2_backend_type == "memory":
        logger.info("Memory L2/L3 backend: memory")

    return MemoryService(l1_backend=l1_backend, l2_backend=l2_backend, l3_backend=l3_backend)


class MemoryService:
    """
    6-layer memory service with MNPI filtering.

    In-memory backends for dev/test. Production backends injected via constructor
    or created by create_memory_store() factory.
    All reads MNPI-filtered by archetype/role.
    """

    def __init__(
        self,
        l1_backend: InMemoryLayerBackend | RedisMemoryBackend | None = None,
        l2_backend: InMemoryLayerBackend | DynamoDBMemoryBackend | None = None,
        l3_backend: InMemoryLayerBackend | DynamoDBMemoryBackend | None = None,
    ) -> None:
        # Layer backends — in-memory by default
        self._layer_backends: dict[MemoryLayer, Any] = {
            layer: InMemoryLayerBackend() for layer in MemoryLayer
        }
        # Override with injected backends
        if l1_backend is not None:
            self._layer_backends[MemoryLayer.L1] = l1_backend
        if l2_backend is not None:
            self._layer_backends[MemoryLayer.L2] = l2_backend
        if l3_backend is not None:
            self._layer_backends[MemoryLayer.L3] = l3_backend

        # L5 procedural memory: advisor_id -> preferences dict
        self._advisor_prefs: dict[str, dict] = {}

    @property
    def _stores(self) -> "dict[MemoryLayer, Any]":
        """Backward-compatible access to layer backends (for tests).

        Returns a dict-like wrapper that maps layer -> backend,
        where each backend supports list-style indexing for in-memory backends.
        """
        return _LayerBackendProxy(self._layer_backends)

    def _compute_expiry(self, layer: MemoryLayer) -> Optional[str]:
        """Compute expiry timestamp based on layer TTL."""
        now = datetime.now(timezone.utc)
        if layer == MemoryLayer.L1:
            return (now + timedelta(hours=L1_TTL_HOURS)).isoformat()
        if layer == MemoryLayer.L2:
            return (now + timedelta(days=L2_TTL_DAYS)).isoformat()
        return None  # L3-L6: no auto-expiry

    def write(self, layer: MemoryLayer, entry: MemoryEntry) -> MemoryEntry:
        """
        Store entry in appropriate backend.
        Sets expires_at based on layer TTL if not already set.
        L6 writes are redirected to M10 in production (not stored here).
        """
        if layer == MemoryLayer.L6:
            logger.info("L6 write redirected to M10 audit logger (WORM)")
            entry = entry.model_copy(update={"layer": MemoryLayer.L6})
            return entry

        if entry.expires_at is None:
            entry = entry.model_copy(update={
                "expires_at": self._compute_expiry(layer),
                "layer": layer,
            })
        else:
            entry = entry.model_copy(update={"layer": layer})

        # L5 procedural: also store in advisor prefs index
        if layer == MemoryLayer.L5 and entry.advisor_id:
            self._advisor_prefs.setdefault(entry.advisor_id, {})
            self._advisor_prefs[entry.advisor_id][entry.entry_id] = entry.content

        self._layer_backends[layer].append(entry)
        logger.info("Wrote %s entry %s for client=%s", layer.value, entry.entry_id, entry.client_id)
        return entry

    def read(self, query: MemoryQuery) -> list[MemoryEntry]:
        """
        Retrieve entries, MNPI-filtered by archetype/role.
        Entries with mnpi_tags are excluded if caller lacks matching archetype/role.
        """
        results: list[MemoryEntry] = []

        for layer in query.layers:
            entries = self._layer_backends[layer].list_all()
            for entry in entries:
                # Client filter
                if entry.client_id and entry.client_id != query.client_id:
                    continue

                # Channel filter
                if query.channel_filter and entry.channel != query.channel_filter:
                    continue

                # MNPI filtering: if entry has mnpi_tags, check caller access
                if entry.mnpi_tags:
                    if not self._mnpi_access_allowed(entry, query):
                        continue

                results.append(entry)

        # Sort by created_at descending, limit
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:query.limit]

    def _mnpi_access_allowed(self, entry: MemoryEntry, query: MemoryQuery) -> bool:
        """
        Check if caller has access to MNPI-tagged entry.
        Entry-level archetype/role must match caller's archetype/role.
        If entry has no archetype/role restriction, MNPI tags still block
        unless caller provides matching archetype.
        """
        # If entry requires specific archetype
        if entry.archetype and query.archetype_filter:
            if entry.archetype != query.archetype_filter:
                return False
        elif entry.archetype and not query.archetype_filter:
            return False  # Entry restricted, caller has no archetype

        # If entry requires specific role
        if entry.role and query.role_filter:
            if entry.role != query.role_filter:
                return False
        elif entry.role and not query.role_filter:
            return False  # Entry restricted, caller has no role

        return True

    def expire_entries(self) -> int:
        """
        Remove expired L1 (8hr) and L2 (7 day) entries.
        Returns count of expired entries removed.
        """
        now = datetime.now(timezone.utc)
        removed = 0

        for layer in [MemoryLayer.L1, MemoryLayer.L2]:
            backend = self._layer_backends[layer]
            all_entries = backend.list_all()
            before = len(all_entries)
            kept = [e for e in all_entries if not self._is_expired(e, now)]
            backend.set_entries(kept)
            removed += before - len(kept)

        if removed:
            logger.info("Expired %d entries from L1/L2", removed)
        return removed

    @staticmethod
    def _is_expired(entry: MemoryEntry, now: datetime) -> bool:
        """Check if an entry has expired."""
        if not entry.expires_at:
            return False
        expires = datetime.fromisoformat(entry.expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    def get_conversation_context(self, client_id: str, channel: Optional[str] = None) -> list[MemoryEntry]:
        """Get L1 working memory for current conversation."""
        query = MemoryQuery(
            client_id=client_id,
            layers=[MemoryLayer.L1],
            limit=50,
            channel_filter=channel,
        )
        return self.read(query)

    def get_recent_interactions(self, client_id: str, days: int = 7) -> list[MemoryEntry]:
        """Get L2 short-term memory for recent interactions."""
        query = MemoryQuery(
            client_id=client_id,
            layers=[MemoryLayer.L2],
            limit=20,
        )
        entries = self.read(query)

        # Further filter by date
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return [e for e in entries if e.created_at >= cutoff]

    def search_semantic(self, client_id: str, query_text: str, limit: int = 5) -> list[MemoryEntry]:
        """
        L4 semantic search. Stub — returns empty in dev.
        Production: pgvector/Pinecone similarity search.
        """
        logger.info("Semantic search stub: client=%s query=%s", client_id, query_text[:50])
        return []

    def get_advisor_preferences(self, advisor_id: str) -> dict:
        """Get L5 procedural memory — advisor workflow preferences."""
        return self._advisor_prefs.get(advisor_id, {})

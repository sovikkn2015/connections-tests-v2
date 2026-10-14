"""
M1 AID Service — core business logic for Agent Identity Documents.

Issues, verifies, and revokes AIDs. JWT RS256 signing.
Key management abstracted via KeyProvider (KMS/Vault/local for dev).

Verify includes an LRU cache because M6 calls verify() on EVERY
request — must be fast. Cache is invalidated on revocation.

This module does NOT import from any other M* module.
Other modules call M1 via REST (FastAPI endpoints in app.py).
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

try:
    from .models import (
        AIDClaims,
        AIDRecord,
        AIDStatus,
        ActorType,
        IssueAIDRequest,
        IssueAIDResponse,
        RevokeAIDResponse,
        VerifyAIDResponse,
    )
except ImportError:
    from models import (
        AIDClaims,
        AIDRecord,
        AIDStatus,
        ActorType,
        IssueAIDRequest,
        IssueAIDResponse,
        RevokeAIDResponse,
        VerifyAIDResponse,
    )

logger = logging.getLogger("m1.aid_service")

# JWT constants
JWT_ALGORITHM = "RS256"
JWT_ISSUER = "007.fsi/m1-identity"


class KeyProvider:
    """
    Abstract key provider for JWT signing/verification.

    Production: AWS KMS, HashiCorp Vault, Azure Key Vault.
    Dev/test: local RSA key pair passed directly.

    Rule 9: Zero credentials in code. Keys injected at runtime.
    """

    def __init__(self, private_key: str, public_key: str) -> None:
        self._private_key = private_key
        self._public_key = public_key

    @property
    def private_key(self) -> str:
        return self._private_key

    @property
    def public_key(self) -> str:
        return self._public_key


class VerifyCache:
    """
    Thread-safe LRU cache for verify() results.

    M6 calls verify() on EVERY request. Caching valid results avoids
    repeated JWT decode + registry lookup. Cache entries are evicted
    on revocation or TTL expiry.

    Production: Redis. Dev/test: in-memory OrderedDict.
    """

    def __init__(self, max_size: int = 1024, ttl_seconds: int = 60) -> None:
        self._cache: OrderedDict[str, tuple[VerifyAIDResponse, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()

    def get(self, token: str) -> Optional[VerifyAIDResponse]:
        """Return cached result if present and not expired."""
        with self._lock:
            entry = self._cache.get(token)
            if entry is None:
                return None
            response, cached_at = entry
            if time.monotonic() - cached_at > self._ttl_seconds:
                del self._cache[token]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(token)
            return response

    def put(self, token: str, response: VerifyAIDResponse) -> None:
        """Cache a valid verify result."""
        with self._lock:
            self._cache[token] = (response, time.monotonic())
            self._cache.move_to_end(token)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, aid_id: str) -> None:
        """Remove all cached entries for a given AID (on revocation)."""
        with self._lock:
            keys_to_remove = [
                k for k, (resp, _) in self._cache.items()
                if resp.aid_id == aid_id
            ]
            for k in keys_to_remove:
                del self._cache[k]


class AIDRegistry:
    """
    In-memory AID registry. Production: PostgreSQL.

    Stores AID records for revocation checks and audit.
    M6 gateway calls verify() on every request — must be fast.
    """

    def __init__(self) -> None:
        self._records: dict[str, AIDRecord] = {}

    def store(self, record: AIDRecord) -> None:
        self._records[record.aid_id] = record

    def get(self, aid_id: str) -> Optional[AIDRecord]:
        return self._records.get(aid_id)

    def revoke(
        self, aid_id: str, revoked_by: str, reason: str
    ) -> Optional[AIDRecord]:
        record = self._records.get(aid_id)
        if record is None:
            return None
        record.status = AIDStatus.revoked
        record.revoked_at = datetime.now(timezone.utc)
        record.revoked_by = revoked_by
        record.revocation_reason = reason
        return record

    def is_revoked(self, aid_id: str) -> bool:
        record = self._records.get(aid_id)
        if record is None:
            return False
        return record.status == AIDStatus.revoked


class PostgresAIDRegistry:
    """
    PostgreSQL-backed AID registry for production.

    Activated when M1_REGISTRY_BACKEND=postgresql and M1_DATABASE_URL is set.
    Uses asyncpg for async connection pooling. Schema auto-created on init.

    Rule 9: No credentials in code — connection string from env var only.
    """

    def __init__(self, pool: "asyncpg.Pool") -> None:  # type: ignore[name-defined]
        self._pool = pool

    @classmethod
    async def create(cls, database_url: str) -> "PostgresAIDRegistry":
        """Factory: create pool + ensure schema exists."""
        try:
            import asyncpg
        except ImportError:
            raise RuntimeError(
                "asyncpg is required for PostgreSQL AID registry. "
                "Install with: pip install asyncpg"
            )
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        instance = cls(pool)
        await instance._ensure_schema()
        logger.info("PostgresAIDRegistry initialized (pool size 2-10)")
        return instance

    async def _ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS aid_records (
                    aid_id       TEXT PRIMARY KEY,
                    record_json  JSONB NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'active',
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_aid_status
                ON aid_records (status)
            """)

    def store(self, record: AIDRecord) -> None:
        """Synchronous store — schedules async write. Use store_async in async context."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.store_async(record))
        except RuntimeError:
            asyncio.run(self.store_async(record))

    async def store_async(self, record: AIDRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO aid_records (aid_id, record_json, status, updated_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (aid_id) DO UPDATE
                SET record_json = $2, status = $3, updated_at = now()
                """,
                record.aid_id,
                record.model_dump_json(),
                record.status.value,
            )

    def get(self, aid_id: str) -> Optional[AIDRecord]:
        """Synchronous get — uses asyncio.run for non-async callers."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.get_async(aid_id))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.get_async(aid_id))

    async def get_async(self, aid_id: str) -> Optional[AIDRecord]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT record_json FROM aid_records WHERE aid_id = $1",
                aid_id,
            )
            if row is None:
                return None
            return AIDRecord.model_validate_json(row["record_json"])

    def revoke(
        self, aid_id: str, revoked_by: str, reason: str
    ) -> Optional[AIDRecord]:
        """Synchronous revoke — delegates to async."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.revoke_async(aid_id, revoked_by, reason),
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(self.revoke_async(aid_id, revoked_by, reason))

    async def revoke_async(
        self, aid_id: str, revoked_by: str, reason: str
    ) -> Optional[AIDRecord]:
        record = await self.get_async(aid_id)
        if record is None:
            return None
        record.status = AIDStatus.revoked
        record.revoked_at = datetime.now(timezone.utc)
        record.revoked_by = revoked_by
        record.revocation_reason = reason
        await self.store_async(record)
        return record

    def is_revoked(self, aid_id: str) -> bool:
        """Synchronous revocation check."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.is_revoked_async(aid_id),
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(self.is_revoked_async(aid_id))

    async def is_revoked_async(self, aid_id: str) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM aid_records WHERE aid_id = $1",
                aid_id,
            )
            if row is None:
                return False
            return row["status"] == AIDStatus.revoked.value


def create_aid_registry() -> AIDRegistry | PostgresAIDRegistry:
    """
    Factory: select AID registry backend based on env var.

    M1_REGISTRY_BACKEND: "memory" (default) or "postgresql"
    M1_DATABASE_URL: PostgreSQL connection string (required for postgresql)

    Returns in-memory registry immediately. PostgreSQL requires async init —
    use create_aid_registry_async() for that.
    """
    backend = os.environ.get("M1_REGISTRY_BACKEND", "memory").lower()
    if backend == "postgresql":
        db_url = os.environ.get("M1_DATABASE_URL")
        if not db_url:
            logger.warning(
                "M1_REGISTRY_BACKEND=postgresql but M1_DATABASE_URL not set. "
                "Falling back to in-memory registry."
            )
            return AIDRegistry()
        logger.info(
            "M1 AID registry backend: postgresql (async init required — "
            "call create_aid_registry_async())"
        )
        # Return in-memory as placeholder; caller must await async init
        return AIDRegistry()
    logger.info("M1 AID registry backend: memory")
    return AIDRegistry()


async def create_aid_registry_async() -> AIDRegistry | PostgresAIDRegistry:
    """
    Async factory: select AID registry backend based on env var.

    M1_REGISTRY_BACKEND: "memory" (default) or "postgresql"
    M1_DATABASE_URL: PostgreSQL connection string (required for postgresql)
    """
    backend = os.environ.get("M1_REGISTRY_BACKEND", "memory").lower()
    if backend == "postgresql":
        db_url = os.environ.get("M1_DATABASE_URL")
        if not db_url:
            logger.warning(
                "M1_REGISTRY_BACKEND=postgresql but M1_DATABASE_URL not set. "
                "Falling back to in-memory registry."
            )
            return AIDRegistry()
        try:
            registry = await PostgresAIDRegistry.create(db_url)
            logger.info("M1 AID registry backend: postgresql (connected)")
            return registry
        except Exception as exc:
            logger.error(
                "Failed to connect to PostgreSQL for AID registry: %s. "
                "Falling back to in-memory.",
                exc,
            )
            return AIDRegistry()
    logger.info("M1 AID registry backend: memory")
    return AIDRegistry()


class AIDService:
    """
    Core AID service. Issues, verifies, revokes Agent Identity Documents.

    Usage:
        key_provider = KeyProvider(private_key_pem, public_key_pem)
        registry = AIDRegistry()
        service = AIDService(key_provider, registry)

        # Issue
        response = service.issue(request)

        # Verify (called by M6 on every request — cached)
        result = service.verify(token)

        # Revoke (immediate — cache invalidated)
        service.revoke(revoke_request, revoked_by="admin@firm.com")

        # Hash for M10 audit logs (privacy — don't store raw AID)
        hashed = AIDService.hash_aid(aid_id)
    """

    def __init__(
        self,
        key_provider: KeyProvider,
        registry: AIDRegistry,
        cache_max_size: int = 1024,
        cache_ttl_seconds: int = 60,
    ) -> None:
        self._keys = key_provider
        self._registry = registry
        self._cache = VerifyCache(
            max_size=cache_max_size, ttl_seconds=cache_ttl_seconds
        )

    def issue(self, request: IssueAIDRequest) -> IssueAIDResponse:
        """Issue a new AID. Returns signed JWT RS256 + metadata."""
        now = datetime.now(timezone.utc)
        aid_id = str(uuid.uuid4())
        expires_at = now + timedelta(hours=request.ttl_hours)

        # Build FSI claims
        claims = AIDClaims(
            actor_type=request.actor_type,
            display_name=request.display_name,
            firm_id=request.firm_id,
            lei=request.lei,
            crd_number=request.crd_number,
            archetype=request.archetype,
            role=request.role,
            jurisdiction=request.jurisdiction,
            authority_scope=request.authority_scope,
            authority_excludes=request.authority_excludes,
            client_scope=request.client_scope,
            pod_id=request.pod_id,
        )

        # Build JWT payload (standard + custom claims)
        payload = {
            # Standard JWT claims
            "iss": JWT_ISSUER,
            "sub": aid_id,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": aid_id,
            # FSI custom claims (exclude_none keeps token compact)
            **claims.model_dump(exclude_none=True),
        }

        # Sign with RS256
        token = jwt.encode(
            payload, self._keys.private_key, algorithm=JWT_ALGORITHM
        )

        # Store in registry
        record = AIDRecord(
            aid_id=aid_id,
            actor_type=request.actor_type,
            display_name=request.display_name,
            firm_id=request.firm_id,
            archetype=request.archetype,
            role=request.role,
            status=AIDStatus.active,
            claims=claims,
            issued_at=now,
            expires_at=expires_at,
            issued_by=JWT_ISSUER,
        )
        self._registry.store(record)

        logger.info(
            "AID issued: %s (actor=%s, role=%s, archetype=%s, firm=%s)",
            aid_id,
            request.actor_type.value,
            request.role.value,
            request.archetype.value,
            request.firm_id,
        )

        return IssueAIDResponse(
            aid_id=aid_id,
            token=token,
            expires_at=expires_at,
            claims=claims,
        )

    def verify(self, token: str) -> VerifyAIDResponse:
        """
        Verify an AID token. Called by M6 on EVERY request.

        Checks: signature, expiry, revocation status.
        Returns claims if valid. Uses LRU cache for performance.
        Never throws — always returns a VerifyAIDResponse.
        """
        # Check cache first
        cached = self._cache.get(token)
        if cached is not None:
            return VerifyAIDResponse(
                valid=cached.valid,
                aid_id=cached.aid_id,
                claims=cached.claims,
                status=cached.status,
                reason=cached.reason,
                cached=True,
            )

        # Decode and validate JWT
        try:
            payload = jwt.decode(
                token,
                self._keys.public_key,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
            )
        except jwt.ExpiredSignatureError:
            return VerifyAIDResponse(valid=False, reason="Token expired")
        except jwt.InvalidIssuerError:
            return VerifyAIDResponse(valid=False, reason="Invalid issuer")
        except jwt.InvalidTokenError as e:
            return VerifyAIDResponse(valid=False, reason=f"Invalid token: {e}")

        aid_id = payload.get("jti")
        if not aid_id:
            return VerifyAIDResponse(valid=False, reason="Missing jti claim")

        # Check revocation in registry
        if self._registry.is_revoked(aid_id):
            return VerifyAIDResponse(
                valid=False,
                aid_id=aid_id,
                reason="Token revoked",
                status=AIDStatus.revoked,
            )

        # Extract and validate FSI claims
        try:
            claims = AIDClaims.model_validate(payload)
        except Exception as e:
            return VerifyAIDResponse(
                valid=False, aid_id=aid_id, reason=f"Invalid claims: {e}"
            )

        # Update verification stats in registry
        record = self._registry.get(aid_id)
        if record:
            record.last_verified_at = datetime.now(timezone.utc)
            record.verification_count += 1

        result = VerifyAIDResponse(
            valid=True,
            aid_id=aid_id,
            claims=claims,
            status=AIDStatus.active,
        )

        # Cache valid results only
        self._cache.put(token, result)

        return result

    def revoke(
        self, request: "RevokeAIDRequest", revoked_by: str
    ) -> RevokeAIDResponse:
        """
        Revoke an AID. Immediate effect.
        Cache is invalidated — M6 verify() will reject on next call.
        """
        record = self._registry.revoke(
            request.aid_id, revoked_by=revoked_by, reason=request.reason
        )
        if record is None:
            raise ValueError(f"AID not found: {request.aid_id}")

        # Invalidate cache immediately
        self._cache.invalidate(request.aid_id)

        logger.info(
            "AID revoked: %s (by=%s, reason=%s)",
            request.aid_id,
            revoked_by,
            request.reason,
        )

        return RevokeAIDResponse(
            aid_id=request.aid_id,
            status=AIDStatus.revoked,
            revoked_at=record.revoked_at,
        )

    @staticmethod
    def hash_aid(aid_id: str) -> str:
        """
        SHA-256 hash of AID for audit logs (Rule 3).
        M10 stores this — not the raw AID — for privacy.
        Returns 64-char lowercase hex string.
        """
        return hashlib.sha256(aid_id.encode("utf-8")).hexdigest()

"""
M10 Audit Logger -- MinIO WORM backend (v0.4.0).

AuditBackend implementation backed by MinIO S3-compatible Object Lock
in Compliance mode. SEC 17a-4(f)(2)(ii) / 17a-4(e)(5) / FINRA 4511
compliant immutable audit store. Drop-in replacement for
``InMemoryAuditBackend(tier="worm")`` in all production values files.

See ``.kiro/specs/m10-worm-minio-backend.md`` for the full contract.

Security invariants (enforced by tests):
* Vault-path-only credentials -- access/secret keys never appear in
  source, in env, in config files, or in any log / exception / repr.
* No process-environment reads in this file (enforced by the existing
  M10 security grep over the source tree).
* Plaintext credentials are function-local in ``__init__`` and are
  released when the constructor returns. Only the ``Minio`` SDK client
  is retained on ``self``.
* COMPLIANCE mode is the default; GOVERNANCE is opt-in with a loud
  ``UserWarning`` at construction.
* Retention floor is 6 years (SEC 17a-4). Enforced at THREE layers:
  the M5 config parse, this backend's constructor, and every
  per-write call (defence-in-depth).
"""

from __future__ import annotations

import io
import json
import re
import warnings
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, Protocol, runtime_checkable

from minio import Minio
from minio.commonconfig import COMPLIANCE, GOVERNANCE
from minio.error import S3Error
from minio.retention import Retention

from m3_schema_registry import AuditEntry

# Import the canonical-JSON helper from the sibling ``logger`` module.
# Same module, different file -- Rule 10 (no cross-module imports)
# permits this.
from m10_audit_logger.logger import (
    AuditWriteError,
    _canonical_json,
)

from m10_audit_logger.backends_minio.legal_hold import (
    HoldEntry,
    LegalHoldError,
)

# =============================================================================
# Constants
# =============================================================================

_MIN_RETENTION_YEARS: int = 6

# Firm IDs become path segments in the object key. Only URL-safe /
# filesystem-safe characters allowed. Rejecting '..', '/', '\0',
# whitespace, and control characters.
_FIRM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")

# SHA-256 hex shape (re-validated here because the backend is a dumb
# store and MUST still reject obviously-invalid seal shapes).
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

# Object metadata keys (MinIO prefixes user-defined metadata with
# ``x-amz-meta-`` when retrieving, but the put-side API expects the
# short key).
_META_SHA256 = "sha256-integrity"
_META_TRACE_ID = "trace-id"
_META_FIRM_ID = "firm-id"

_VALID_MODES = {"COMPLIANCE", "GOVERNANCE"}
_MODE_TO_SDK = {"COMPLIANCE": COMPLIANCE, "GOVERNANCE": GOVERNANCE}

# Endpoint URL: ``http[s]://host[:port][/path]``.
_ENDPOINT_URL_RE = re.compile(
    r"^(?P<scheme>https?)://(?P<host>[A-Za-z0-9._\-]+(?::[0-9]{1,5})?)(?:/.*)?$"
)


# =============================================================================
# Protocols (injectable contracts)
# =============================================================================


@runtime_checkable
class VaultClient(Protocol):
    """Narrow read-only Vault interface.

    Production wiring uses a HashiCorp-Vault-or-AWS-Secrets-Manager
    adapter (shared infra; out of scope for this backend's spec).
    Tests inject ``FakeVaultClient``. The contract is deliberately
    minimal so swapping adapters is mechanical.
    """

    def read_secret(self, path: str) -> str: ...


@runtime_checkable
class MinIOWormConfigProtocol(Protocol):
    """Duck-typed view of the M5 ``MinIOWormConfig`` Pydantic model.

    Keeping the backend free of an ``m5_config_loader`` import
    (Rule 10). The M5 Pydantic model naturally satisfies this
    Protocol; tests pass a lightweight dataclass-equivalent with the
    same field names.
    """

    endpoint_url: str
    bucket_name: str
    region: str
    access_key_vault_path: str
    secret_key_vault_path: str
    retention_years: int
    object_lock_mode: Literal["COMPLIANCE", "GOVERNANCE"]
    secure: bool


# =============================================================================
# Helpers
# =============================================================================


def _parse_endpoint(endpoint_url: str) -> tuple[str, bool]:
    """Split ``https://host:9000`` into ``("host:9000", True)``.

    The MinIO SDK wants host-only (or host:port) + a separate
    ``secure`` boolean. We refuse anything that isn't ``http`` or
    ``https``.
    """
    m = _ENDPOINT_URL_RE.match(endpoint_url or "")
    if not m:
        raise AuditWriteError("worm_write_failed")
    return m.group("host"), m.group("scheme") == "https"


def _to_utc(dt: datetime) -> datetime:
    """Return a UTC-normalised datetime. Raise on naive input."""
    if not isinstance(dt, datetime):
        raise AuditWriteError("worm_write_failed")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise AuditWriteError("worm_write_failed")
    return dt.astimezone(timezone.utc)


def _build_object_key(firm_id: str, timestamp: datetime, canonical_id) -> str:
    """Construct ``{firm_id}/{yyyy}/{mm}/{dd}/{canonical_id}.json``.

    Deterministic across identical inputs. Raises if ``firm_id`` is
    unsafe for a path segment.
    """
    if not isinstance(firm_id, str) or not _FIRM_ID_PATTERN.fullmatch(firm_id):
        raise AuditWriteError("worm_write_failed")
    dt = _to_utc(timestamp)
    return (
        f"{firm_id}/"
        f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/"
        f"{canonical_id}.json"
    )


# =============================================================================
# Backend
# =============================================================================


class MinIOWormBackend:
    """AuditBackend backed by MinIO Object Lock in Compliance mode.

    SEC 17a-4(f)(2)(ii) WORM storage. 6-year minimum retention.
    Tamper-evident via SHA-256 integrity hash attached as object
    metadata. Fail-closed on any configuration or connectivity error.

    Args:
        config: Duck-typed ``MinIOWormConfigProtocol`` (the M5
            Pydantic model ``MinIOWormConfig`` satisfies this shape).
        vault_client: ``VaultClient`` used to fetch access+secret
            keys at construction time. Plaintext credentials live
            ONLY inside ``__init__`` and are released on return.
        minio_client_factory: Optional test hook. Production omits
            it and the constructor uses ``minio.Minio``.

    Raises:
        AuditWriteError("worm_write_failed") on any construction-time
            failure: bad config, missing Vault secret, bucket
            misconfiguration, Object Lock not enabled, mode mismatch.
    """

    # Class-level ``tier`` satisfies the AuditBackend Protocol and the
    # ``invalid_backend_tier`` check in ``AuditLogger``.
    tier: str = "worm"

    def __init__(
        self,
        *,
        config: MinIOWormConfigProtocol,
        vault_client: VaultClient,
        minio_client_factory=None,
        legal_hold_bucket_name: str = "007-audit-legal-holds",
        orchestrator=None,
    ) -> None:
        # ----- config validation (defence-in-depth vs M5 parse) -----
        retention_years = getattr(config, "retention_years", None)
        if (
            not isinstance(retention_years, int)
            or retention_years < _MIN_RETENTION_YEARS
        ):
            raise AuditWriteError("worm_write_failed")

        mode = getattr(config, "object_lock_mode", None)
        if mode not in _VALID_MODES:
            raise AuditWriteError("worm_write_failed")

        bucket = getattr(config, "bucket_name", None)
        if not isinstance(bucket, str) or not bucket:
            raise AuditWriteError("worm_write_failed")

        endpoint_url = getattr(config, "endpoint_url", None)
        if not isinstance(endpoint_url, str):
            raise AuditWriteError("worm_write_failed")
        host, endpoint_is_secure = _parse_endpoint(endpoint_url)

        region = getattr(config, "region", None)
        if not isinstance(region, str) or not region:
            raise AuditWriteError("worm_write_failed")

        config_secure = bool(getattr(config, "secure", endpoint_is_secure))
        # If the endpoint is https, secure MUST be True (defensive).
        if endpoint_is_secure and not config_secure:
            raise AuditWriteError("worm_write_failed")

        if mode == "GOVERNANCE":
            warnings.warn(
                "MinIOWormBackend: object_lock_mode=GOVERNANCE -- a "
                "privileged compliance officer can release the lock. "
                "COMPLIANCE is the SEC 17a-4 default.",
                UserWarning,
                stacklevel=2,
            )

        # ----- credential fetch (Vault only) -----
        access_key_path = getattr(config, "access_key_vault_path", None)
        secret_key_path = getattr(config, "secret_key_vault_path", None)
        if not isinstance(access_key_path, str) or not isinstance(
            secret_key_path, str
        ):
            raise AuditWriteError("worm_write_failed")

        try:
            access_key = vault_client.read_secret(access_key_path)
            secret_key = vault_client.read_secret(secret_key_path)
        except Exception:
            # Swallow the original exception to avoid leaking any
            # Vault-adapter metadata (which may include path fragments)
            # into the AuditWriteError message. Reason is frozen.
            raise AuditWriteError("worm_write_failed")

        if not isinstance(access_key, str) or not access_key:
            raise AuditWriteError("worm_write_failed")
        if not isinstance(secret_key, str) or not secret_key:
            raise AuditWriteError("worm_write_failed")

        # ----- MinIO client (factory indirection for tests) -----
        factory = minio_client_factory if minio_client_factory is not None else Minio
        try:
            client = factory(
                endpoint=host,
                access_key=access_key,
                secret_key=secret_key,
                secure=config_secure,
                region=region,
            )
        except Exception:
            raise AuditWriteError("worm_write_failed")
        finally:
            # Release plaintext keys from local scope. CPython will
            # refcount-release at end-of-scope anyway; this is a
            # deliberate signal to any future reader that credentials
            # MUST NOT outlive this block.
            access_key = None  # noqa: F841
            secret_key = None  # noqa: F841

        # ----- retained state (no credentials) -----
        self._client = client
        self._bucket: str = bucket
        self._endpoint: str = host
        self._secure: bool = config_secure
        self._region: str = region
        self._retention_years: int = retention_years
        self._mode: Literal["COMPLIANCE", "GOVERNANCE"] = mode
        # Wave 4: legal-hold registry bucket + optional audit orchestrator.
        self._legal_hold_bucket: str = legal_hold_bucket_name
        self._orchestrator = orchestrator

        # ----- startup health check -----
        self._verify_bucket_configuration()
        self._verify_legal_hold_bucket_configuration()

    # -------------------------------------------------------------------------
    # AuditBackend Protocol surface
    # -------------------------------------------------------------------------

    def write(self, entry: AuditEntry) -> None:
        """Upload one sealed AuditEntry to the WORM bucket.

        Raises AuditWriteError("worm_write_failed") on any failure.
        Never mutates ``entry``.
        """
        if not isinstance(entry, AuditEntry):
            raise AuditWriteError("worm_write_failed")

        # Integrity-hash shape check (orchestrator already sealed).
        integrity = getattr(entry, "sha256_integrity", "")
        if not isinstance(integrity, str) or not _SHA256_HEX.fullmatch(
            integrity
        ):
            raise AuditWriteError("worm_write_failed")

        # Retention floor (defence-in-depth).
        retention_years = entry.retention_years
        if (
            not isinstance(retention_years, int)
            or retention_years < _MIN_RETENTION_YEARS
        ):
            raise AuditWriteError("worm_write_failed")

        # Timezone + firm_id validation happens inside _build_object_key.
        object_key = _build_object_key(
            entry.firm_id, entry.timestamp, entry.canonical_id
        )

        # retain_until = EVENT timestamp + retention_years (SEC 17a-4
        # retention clock starts at the event, not at the upload).
        retain_until = _to_utc(entry.timestamp) + timedelta(
            days=365 * retention_years
        )

        # Canonical-JSON serialisation so the on-disk bytes are
        # byte-stable. (Same canonicalisation the integrity hash used.)
        body_bytes = _canonical_json(
            entry.model_dump(mode="json")
        ).encode("utf-8")

        metadata = {
            _META_SHA256: integrity,
            _META_TRACE_ID: str(entry.trace_id),
            _META_FIRM_ID: entry.firm_id,
        }

        retention = Retention(
            mode=_MODE_TO_SDK[self._mode],
            retain_until_date=retain_until,
        )

        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_key,
                data=io.BytesIO(body_bytes),
                length=len(body_bytes),
                content_type="application/json",
                metadata=metadata,
                retention=retention,
                legal_hold=False,
            )
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            # Any other SDK/IO failure also means the WORM write did
            # not persist; fail-closed.
            raise AuditWriteError("worm_write_failed")

    def query_by_trace_id(
        self,
        trace_id: str,
        *,
        firm_id_hint: Optional[str] = None,
    ) -> list[AuditEntry]:
        """Debug-only scan for matching entries.

        O(N) in the bucket (or the ``firm_id_hint`` prefix). Not
        production scalable; Phase 4 adds an Elasticsearch index.

        Raises AuditWriteError("worm_write_failed") on any listing or
        read failure -- callers may catch this if they want to
        continue past partial failures.
        """
        if not isinstance(trace_id, str) or not trace_id:
            return []

        if firm_id_hint is not None:
            if not _FIRM_ID_PATTERN.fullmatch(firm_id_hint):
                raise AuditWriteError("worm_write_failed")
            prefix = f"{firm_id_hint}/"
        else:
            prefix = ""

        results: list[AuditEntry] = []
        try:
            objects = list(
                self._client.list_objects(
                    self._bucket,
                    prefix=prefix,
                    recursive=True,
                )
            )
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            raise AuditWriteError("worm_write_failed")

        for obj in objects:
            try:
                response = self._client.get_object(
                    self._bucket, obj.object_name
                )
                try:
                    body = response.read()
                finally:
                    # ``minio`` response objects expose both close() and
                    # release_conn() when backed by urllib3; guard.
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
                    release = getattr(response, "release_conn", None)
                    if callable(release):
                        release()
                parsed = json.loads(body.decode("utf-8"))
                entry = AuditEntry.model_validate(parsed)
            except S3Error:
                raise AuditWriteError("worm_write_failed")
            except Exception:
                raise AuditWriteError("worm_write_failed")

            if entry.trace_id == trace_id:
                results.append(entry)

        return results

    # -------------------------------------------------------------------------
    # Legal-hold API (FINRA 4511.04) -- v0.5.0.
    # -------------------------------------------------------------------------

    def place_legal_hold(
        self,
        canonical_id,
        hold_id: str,
        reason: str,
        placed_by: str,
        *,
        now: Optional[datetime] = None,
    ) -> HoldEntry:
        """Place a FINRA 4511.04 legal hold on one audit entry.

        Flow:
            1. Locate the target version of the audit object (stat).
            2. Ensure no active hold with the same hold_id exists.
            3. Write the HoldEntry JSON to the registry bucket
               (6-year COMPLIANCE retention applies).
            4. Toggle MinIO's object-level LegalHold flag ON.
            5. Emit an audit record via the orchestrator (if present)
               and (non-recursively) legal-hold that audit record too
               with hold_id ``f"meta-{hold_id}"``.

        Returns the ``HoldEntry`` that was written.

        Raises ``LegalHoldError`` on duplicate / missing / backend
        failures. Never raises AuditWriteError from here -- the two
        error families are distinct (audit writes vs hold management).
        """
        entry = self._build_hold_entry(
            canonical_id=canonical_id,
            hold_id=hold_id,
            reason=reason,
            placed_by=placed_by,
            placed_at=self._now(now),
        )

        # Resolve the target version. Also validates that the target
        # audit entry exists -- LegalHoldError("target_not_found").
        target_object_name, target_version_id, target_firm_id = (
            self._resolve_target_version(entry.canonical_id)
        )

        # Reject duplicate hold_id for this canonical_id.
        registry_key = self._legal_hold_registry_key(
            entry.canonical_id, entry.hold_id
        )
        existing = self._read_registry_object(registry_key)
        if existing is not None and existing.is_active:
            raise LegalHoldError("duplicate_hold_id")

        # Step 3: write the registry object.
        self._write_registry_object(registry_key, entry)

        # Step 4: toggle LegalHold ON.
        try:
            self._client.enable_object_legal_hold(
                bucket_name=self._bucket,
                object_name=target_object_name,
                version_id=target_version_id,
            )
        except Exception:
            # Best effort -- the hold registry is the durable record.
            # Surface as a typed error, but don't try to unwind the
            # registry write (Object Lock would reject a delete anyway).
            raise LegalHoldError("legal_hold_write_failed")

        # Step 5: audit emission + meta-hold (not recursive -- meta
        # holds do NOT themselves receive a further meta-hold). This
        # is deliberately lenient: if the audit orchestrator fails, the
        # MinIO-level legal-hold flag is already on and the tamper-
        # evidence remains sound; we do NOT unwind.
        if (
            self._orchestrator is not None
            and not entry.hold_id.startswith("meta-")
        ):
            self._emit_legal_hold_audit(
                entry,
                action="legal_hold.placed",
                actor=placed_by,
                target_firm_id=target_firm_id,
                registry_key=registry_key,
            )
        return entry

    def release_legal_hold(
        self,
        canonical_id,
        hold_id: str,
        reason: str,
        released_by: str,
        *,
        now: Optional[datetime] = None,
    ) -> HoldEntry:
        """Release an active hold referenced by ``hold_id``.

        Rejects if no active hold exists with this hold_id (AC4.3) or
        if the hold is already released (AC4.4).
        """
        registry_key = self._legal_hold_registry_key(canonical_id, hold_id)
        existing = self._read_registry_object(registry_key)
        if existing is None:
            raise LegalHoldError("hold_not_found")
        if not existing.is_active:
            raise LegalHoldError("hold_already_released")

        # Validate actor shape.
        if not isinstance(released_by, str) or not _SHA256_HEX.fullmatch(
            released_by
        ):
            raise LegalHoldError("legal_hold_write_failed")

        released_at = self._now(now)
        released_entry = HoldEntry(
            hold_id=existing.hold_id,
            canonical_id=existing.canonical_id,
            reason=reason,
            placed_by=existing.placed_by,
            placed_at=existing.placed_at,
            released_at=released_at,
            released_by=released_by,
        )

        # Resolve target for the MinIO flag toggle + for audit.
        target_object_name, target_version_id, target_firm_id = (
            self._resolve_target_version(existing.canonical_id)
        )

        # Registry is versioned + Object-Lock-protected; this is an
        # append-a-new-version write, not a mutation of the original.
        self._write_registry_object(registry_key, released_entry)

        # Toggle LegalHold OFF.
        try:
            self._client.disable_object_legal_hold(
                bucket_name=self._bucket,
                object_name=target_object_name,
                version_id=target_version_id,
            )
        except Exception:
            raise LegalHoldError("legal_hold_write_failed")

        if (
            self._orchestrator is not None
            and not released_entry.hold_id.startswith("meta-")
        ):
            self._emit_legal_hold_audit(
                released_entry,
                action="legal_hold.released",
                actor=released_by,
                target_firm_id=target_firm_id,
                registry_key=registry_key,
            )
        return released_entry

    def list_legal_holds(self, canonical_id) -> list[HoldEntry]:
        """Return ACTIVE holds for ``canonical_id``, sorted by placed_at."""
        prefix = f"{canonical_id}/"
        try:
            objects = list(
                self._client.list_objects(
                    self._legal_hold_bucket,
                    prefix=prefix,
                    recursive=True,
                )
            )
        except Exception:
            raise LegalHoldError("legal_hold_registry_failed")

        results: list[HoldEntry] = []
        for obj in objects:
            entry = self._read_registry_object(obj.object_name)
            if entry is not None and entry.is_active:
                results.append(entry)

        results.sort(key=lambda e: e.placed_at)
        return results

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        # Bucket + endpoint + mode + retention -- never the keys.
        return (
            f"MinIOWormBackend(tier={self.tier!r}, "
            f"bucket={self._bucket!r}, "
            f"endpoint={self._endpoint!r}, "
            f"secure={self._secure!r}, "
            f"region={self._region!r}, "
            f"object_lock_mode={self._mode!r}, "
            f"retention_years={self._retention_years})"
        )

    __str__ = __repr__

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _verify_bucket_configuration(self) -> None:
        """Assert bucket exists AND Object Lock is in the expected mode.

        Runs once at construction. Any failure -> fail-closed.
        """
        try:
            exists = self._client.bucket_exists(self._bucket)
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            raise AuditWriteError("worm_write_failed")
        if not exists:
            raise AuditWriteError("worm_write_failed")

        try:
            cfg = self._client.get_object_lock_config(self._bucket)
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            raise AuditWriteError("worm_write_failed")

        if cfg is None:
            raise AuditWriteError("worm_write_failed")
        observed_mode = getattr(cfg, "mode", None)
        if observed_mode != self._mode:
            raise AuditWriteError("worm_write_failed")

    # -------------------------------------------------------------------------
    # Legal-hold internals (v0.5.0).
    # -------------------------------------------------------------------------

    def _verify_legal_hold_bucket_configuration(self) -> None:
        """Assert the registry bucket exists with Object Lock in the
        same mode as the primary WORM bucket.

        Fail-closed on any mismatch -- a mis-provisioned registry is a
        tamper vector.
        """
        try:
            exists = self._client.bucket_exists(self._legal_hold_bucket)
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            raise AuditWriteError("worm_write_failed")
        if not exists:
            raise AuditWriteError("worm_write_failed")

        try:
            cfg = self._client.get_object_lock_config(self._legal_hold_bucket)
        except S3Error:
            raise AuditWriteError("worm_write_failed")
        except Exception:
            raise AuditWriteError("worm_write_failed")

        if cfg is None:
            raise AuditWriteError("worm_write_failed")
        observed_mode = getattr(cfg, "mode", None)
        if observed_mode != self._mode:
            raise AuditWriteError("worm_write_failed")

    @staticmethod
    def _now(override: Optional[datetime]) -> datetime:
        if override is not None:
            if override.tzinfo is None or override.utcoffset() is None:
                raise LegalHoldError("legal_hold_write_failed")
            return override.astimezone(timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _legal_hold_registry_key(canonical_id, hold_id: str) -> str:
        return f"{canonical_id}/{hold_id}.json"

    @staticmethod
    def _build_hold_entry(
        *,
        canonical_id,
        hold_id: str,
        reason: str,
        placed_by: str,
        placed_at: datetime,
    ) -> HoldEntry:
        """Construct a strict HoldEntry; translate Pydantic errors."""
        try:
            return HoldEntry(
                hold_id=hold_id,
                canonical_id=canonical_id,
                reason=reason,
                placed_by=placed_by,
                placed_at=placed_at,
            )
        except Exception:
            raise LegalHoldError("legal_hold_write_failed")

    def _resolve_target_version(self, canonical_id):
        """Locate ``{firm}/YYYY/MM/DD/{canonical_id}.json`` in the WORM
        bucket and return (object_name, version_id, firm_id).

        O(N) in the bucket -- documented as non-scalable; Phase 4 adds
        an index. Raises LegalHoldError("target_not_found") if no
        object matches.
        """
        needle = f"/{canonical_id}.json"
        try:
            objects = list(
                self._client.list_objects(
                    self._bucket,
                    prefix="",
                    recursive=True,
                )
            )
        except Exception:
            raise LegalHoldError("legal_hold_registry_failed")

        for obj in objects:
            name = obj.object_name or ""
            if not name.endswith(needle):
                continue
            # Firm is the first path segment.
            firm_id = name.split("/", 1)[0]
            version_id = getattr(obj, "version_id", None)
            return name, version_id, firm_id

        raise LegalHoldError("target_not_found")

    def _read_registry_object(self, key: str) -> Optional[HoldEntry]:
        """Return the registry HoldEntry at ``key`` or None if missing.

        Raises LegalHoldError("legal_hold_registry_failed") on any
        non-404 backend error.
        """
        try:
            response = self._client.get_object(
                self._legal_hold_bucket, key
            )
        except S3Error as err:
            if getattr(err, "code", "") in (
                "NoSuchKey",
                "NoSuchObject",
                "NoSuchBucketKey",
            ):
                return None
            raise LegalHoldError("legal_hold_registry_failed")
        except Exception:
            raise LegalHoldError("legal_hold_registry_failed")

        try:
            try:
                body = response.read()
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                release = getattr(response, "release_conn", None)
                if callable(release):
                    release()
            # Use model_validate_json so ISO-8601 strings and UUID
            # strings from the canonical-JSON-serialised registry
            # object are parsed correctly under strict mode.
            return HoldEntry.model_validate_json(body)
        except Exception:
            raise LegalHoldError("legal_hold_registry_failed")

    def _write_registry_object(self, key: str, entry: HoldEntry) -> None:
        """Write the HoldEntry canonical JSON to the registry bucket
        with 6-year COMPLIANCE retention.
        """
        body_bytes = _canonical_json(entry.model_dump(mode="json")).encode(
            "utf-8"
        )
        retain_until = _to_utc(entry.placed_at) + timedelta(
            days=365 * self._retention_years
        )
        retention = Retention(
            mode=_MODE_TO_SDK[self._mode],
            retain_until_date=retain_until,
        )
        try:
            self._client.put_object(
                bucket_name=self._legal_hold_bucket,
                object_name=key,
                data=io.BytesIO(body_bytes),
                length=len(body_bytes),
                content_type="application/json",
                metadata={
                    "hold-id": entry.hold_id,
                    "canonical-id": str(entry.canonical_id),
                    "is-active": "true" if entry.is_active else "false",
                },
                retention=retention,
                legal_hold=False,
            )
        except Exception:
            raise LegalHoldError("legal_hold_registry_failed")

    def _emit_legal_hold_audit(
        self,
        entry: HoldEntry,
        *,
        action: str,
        actor: str,
        target_firm_id: str,
        registry_key: str,
    ) -> None:
        """Emit an audit record for the hold event AND meta-hold it.

        If the orchestrator is unset (library-only mode) this is a
        no-op -- the caller has already validated that condition.
        """
        import hashlib
        from uuid import uuid4 as _uuid4

        hold_canonical = _uuid4()
        entry_sha = hashlib.sha256(
            _canonical_json(entry.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()

        audit = AuditEntry(
            canonical_id=hold_canonical,
            trace_id=f"legal-hold:{entry.hold_id}",
            timestamp=entry.placed_at if entry.released_at is None else entry.released_at,
            actor_id=actor,
            action=action,
            module="m10",
            target_type="audit_entry",
            target_id=str(entry.canonical_id),
            decision="allow",
            reason=entry.reason[:512],
            input_hash=entry_sha,
            output_hash=entry_sha,
            latency_ms=0,
            firm_id=target_firm_id,
            worm_record_id=f"legal-hold/{entry.canonical_id}/{entry.hold_id}",
            sha256_integrity="",
            retention_years=self._retention_years,
        )
        try:
            self._orchestrator.write(audit)
        except Exception:
            # Tamper-evidence already achieved at MinIO level. Audit
            # failure is surfaced to the DLQ by the orchestrator; we
            # deliberately do NOT re-raise here.
            return

        # Meta-hold: hold the legal-hold audit entry itself so the
        # tamper record cannot be tampered with.
        try:
            self.place_legal_hold(
                canonical_id=hold_canonical,
                hold_id=f"meta-{entry.hold_id}",
                reason=f"meta-hold for {action}",
                placed_by=actor,
                now=audit.timestamp,
            )
        except LegalHoldError:
            # The audit record is written; meta-hold failure is
            # surfaced to operator logs (already emitted via
            # orchestrator tier). Do NOT unwind.
            return

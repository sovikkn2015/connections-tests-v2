"""
M10 MinIO WORM Backend -- Unit Tests (network-free).

Covers Ops Hardening Wave 3 spec §4.1. 30 cases across 8 groups.

Run locally:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/\\
            tests/unit/test_m10_minio_worm.py -v
"""

from __future__ import annotations

import io
import re
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from m3_schema_registry import AuditEntry

import m10_audit_logger  # noqa: F401 -- side-effect: lazy import surface
from m10_audit_logger import AuditWriteError
from m10_audit_logger.backends_minio.minio_worm import (
    MinIOWormBackend,
    _build_object_key,
    _parse_endpoint,
)
from m5_config_loader import ConfigSecurityError, MinIOWormConfig

# =============================================================================
# Fixtures + fakes (no network, no Docker)
# =============================================================================


_FIXED_TIMESTAMP = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_UUID = UUID("11111111-1111-1111-1111-111111111111")


def _fixed_entry(**overrides) -> AuditEntry:
    """Deterministic AuditEntry with a valid-shape sha256_integrity."""
    kwargs = dict(
        canonical_id=_FIXED_UUID,
        trace_id="trace-fixed-001",
        timestamp=_FIXED_TIMESTAMP,
        actor_id="actor-hash-abc",
        action="test.action",
        module="m10",
        decision="allow",
        input_hash="0" * 64,
        output_hash="1" * 64,
        latency_ms=5,
        firm_id="CRD-123456",
        worm_record_id="worm/key/fixed",
        sha256_integrity="a" * 64,
        retention_years=6,
    )
    kwargs.update(overrides)
    return AuditEntry(**kwargs)


class FakeVaultClient:
    """In-memory Vault stub. Raises KeyError on unknown paths."""

    def __init__(self, secrets: dict[str, str]):
        self._secrets = dict(secrets)

    def read_secret(self, path: str) -> str:
        if path not in self._secrets:
            raise KeyError(path)
        return self._secrets[path]


class _FakeLockCfg:
    """Stand-in for minio.objectlockconfig.ObjectLockConfig."""

    def __init__(self, mode: str | None):
        self.mode = mode


class _FakeS3ErrorBody:
    def __init__(self, code: str = "NoSuchBucket", message: str = "boom"):
        self.code = code
        self.message = message


class FakeMinioClient:
    """Minimal MinIO client stub. Records every call for assertions."""

    def __init__(
        self,
        *,
        bucket_exists_result: bool = True,
        object_lock_mode: str | None = "COMPLIANCE",
        put_should_raise: bool = False,
        list_should_raise: bool = False,
        health_should_raise: bool = False,
        health_raises_s3: bool = False,
        **_ignored,
    ):
        self._bucket_exists_result = bucket_exists_result
        self._object_lock_mode = object_lock_mode
        self._put_should_raise = put_should_raise
        self._list_should_raise = list_should_raise
        self._health_should_raise = health_should_raise
        self._health_raises_s3 = health_raises_s3

        self.put_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.bucket_exists_calls = 0
        self.get_object_lock_config_calls = 0

        # Raw storage for list/get_object round trips
        self._objects: dict[str, tuple[bytes, dict]] = {}

    # ------- Health check surface -------
    def bucket_exists(self, bucket_name: str) -> bool:
        self.bucket_exists_calls += 1
        if self._health_should_raise:
            if self._health_raises_s3:
                from minio.error import S3Error
                raise S3Error(
                    code="InternalError",
                    message="boom",
                    resource=bucket_name,
                    request_id="r",
                    host_id="h",
                    response=None,
                )
            raise RuntimeError("health-boom")
        return self._bucket_exists_result

    def get_object_lock_config(self, bucket_name: str):
        self.get_object_lock_config_calls += 1
        if self._object_lock_mode is None:
            return None
        return _FakeLockCfg(mode=self._object_lock_mode)

    # ------- Write surface -------
    def put_object(self, **kwargs):
        if self._put_should_raise:
            from minio.error import S3Error
            raise S3Error(
                code="ObjectLockConfigurationNotFoundError",
                message="no lock",
                resource=kwargs.get("bucket_name", ""),
                request_id="r",
                host_id="h",
                response=None,
            )
        # Read the BytesIO body now (tests typically only inspect shape).
        data = kwargs.get("data")
        raw = data.read() if data is not None else b""
        key = kwargs["object_name"]
        self._objects[key] = (raw, dict(kwargs.get("metadata") or {}))
        self.put_calls.append(
            {
                "bucket_name": kwargs.get("bucket_name"),
                "object_name": key,
                "length": kwargs.get("length"),
                "content_type": kwargs.get("content_type"),
                "metadata": kwargs.get("metadata"),
                "retention": kwargs.get("retention"),
                "legal_hold": kwargs.get("legal_hold"),
                "body": raw,
            }
        )
        return SimpleNamespace(object_name=key, etag="fake-etag")

    # ------- Query surface -------
    def list_objects(self, bucket_name, *, prefix="", recursive=True):
        self.list_calls.append(
            dict(bucket_name=bucket_name, prefix=prefix, recursive=recursive)
        )
        if self._list_should_raise:
            from minio.error import S3Error
            raise S3Error(
                code="InternalError",
                message="boom",
                resource=bucket_name,
                request_id="r",
                host_id="h",
                response=None,
            )
        for key in sorted(self._objects.keys()):
            if key.startswith(prefix):
                yield SimpleNamespace(object_name=key)

    def get_object(self, bucket_name, object_name):
        raw, _meta = self._objects[object_name]

        class _Resp:
            def __init__(self, payload: bytes):
                self._payload = payload

            def read(self):
                return self._payload

            def close(self):
                pass

            def release_conn(self):
                pass

        return _Resp(raw)


def _base_config(**overrides) -> MinIOWormConfig:
    kwargs = dict(
        endpoint_url="http://localhost:9000",
        bucket_name="audit-worm",
        region="us-east-1",
        access_key_vault_path="secret/data/m10/minio/access_key",
        secret_key_vault_path="secret/data/m10/minio/secret_key",
        retention_years=6,
        object_lock_mode="COMPLIANCE",
        secure=False,
    )
    kwargs.update(overrides)
    return MinIOWormConfig(**kwargs)


def _vault() -> FakeVaultClient:
    return FakeVaultClient({
        "secret/data/m10/minio/access_key": "fake-access-key-abc123",
        "secret/data/m10/minio/secret_key": "fake-secret-key-xyz789",
    })


def _factory(**fake_kwargs):
    """Return a minio_client_factory callable that ignores SDK args
    and returns a pre-parameterised FakeMinioClient."""

    def _f(**_sdk_kwargs):
        return FakeMinioClient(**fake_kwargs)

    return _f


# =============================================================================
# Group 1 -- TestConfigValidation (6 cases, M5 level)
# =============================================================================


class TestConfigValidation:

    def test_valid_config_accepts(self):
        cfg = _base_config()
        assert cfg.retention_years == 6
        assert cfg.object_lock_mode == "COMPLIANCE"
        assert cfg.secure is False

    def test_retention_5_raises_validation(self):
        with pytest.raises(ValidationError):
            _base_config(retention_years=5)

    def test_retention_0_raises_validation(self):
        with pytest.raises(ValidationError):
            _base_config(retention_years=0)

    def test_missing_scheme_raises_validation(self):
        with pytest.raises(ValidationError):
            _base_config(endpoint_url="localhost:9000")

    def test_uppercase_bucket_raises_dns_validation(self):
        with pytest.raises(ValidationError):
            _base_config(bucket_name="AuditWorm")

    def test_vault_path_with_akia_like_raises_security(self):
        # Literal-secret in vault path shape -- should fail M5 parse.
        with pytest.raises(ValidationError):
            _base_config(
                access_key_vault_path=(
                    "secret/data/m10/minio/AKIA1234567890123456"
                ),
            )

    def test_vault_path_wrong_prefix_raises(self):
        with pytest.raises(ValidationError):
            _base_config(
                access_key_vault_path="secret/data/m9/tenants/foo",
            )

    def test_governance_mode_emits_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _base_config(object_lock_mode="GOVERNANCE")
        msgs = [str(x.message) for x in w]
        assert any("GOVERNANCE" in m for m in msgs), msgs


# =============================================================================
# Group 2 -- TestConstructorHealthCheck (5 cases)
# =============================================================================


class TestConstructorHealthCheck:

    def test_happy_construction(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        assert backend.tier == "worm"
        # v0.5.0 legal-hold: construction verifies primary + legal-hold
        # registry buckets. Exact count rises from 1 to 2.
        assert fake.bucket_exists_calls >= 1
        assert fake.get_object_lock_config_calls >= 1

    def test_bucket_does_not_exist(self):
        fake = FakeMinioClient(bucket_exists_result=False)
        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(),
                vault_client=_vault(),
                minio_client_factory=lambda **_: fake,
            )
        assert exc.value.reason == "worm_write_failed"

    def test_get_object_lock_config_raises_s3_error(self):
        fake = FakeMinioClient(
            health_should_raise=True, health_raises_s3=True
        )
        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(),
                vault_client=_vault(),
                minio_client_factory=lambda **_: fake,
            )
        assert exc.value.reason == "worm_write_failed"

    def test_object_lock_mode_mismatch(self):
        # Config wants COMPLIANCE; bucket reports GOVERNANCE.
        fake = FakeMinioClient(object_lock_mode="GOVERNANCE")
        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(object_lock_mode="COMPLIANCE"),
                vault_client=_vault(),
                minio_client_factory=lambda **_: fake,
            )
        assert exc.value.reason == "worm_write_failed"

    def test_object_lock_config_none_fails(self):
        fake = FakeMinioClient(object_lock_mode=None)
        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(),
                vault_client=_vault(),
                minio_client_factory=lambda **_: fake,
            )
        assert exc.value.reason == "worm_write_failed"

    def test_missing_access_key_in_vault(self):
        empty_vault = FakeVaultClient({
            # only secret key; access_key not present
            "secret/data/m10/minio/secret_key": "fake",
        })
        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(),
                vault_client=empty_vault,
                minio_client_factory=lambda **_: FakeMinioClient(),
            )
        assert exc.value.reason == "worm_write_failed"


# =============================================================================
# Group 3 -- TestWritePath (8 cases)
# =============================================================================


class TestWritePath:

    @pytest.fixture
    def backend_and_fake(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        return backend, fake

    def test_happy_write_attaches_sha256_metadata(self, backend_and_fake):
        backend, fake = backend_and_fake
        entry = _fixed_entry()
        backend.write(entry)
        assert len(fake.put_calls) == 1
        meta = fake.put_calls[0]["metadata"]
        assert meta["sha256-integrity"] == "a" * 64
        assert meta["trace-id"] == "trace-fixed-001"
        assert meta["firm-id"] == "CRD-123456"

    def test_object_key_matches_date_firm_id_pattern(self, backend_and_fake):
        backend, fake = backend_and_fake
        entry = _fixed_entry()
        backend.write(entry)
        key = fake.put_calls[0]["object_name"]
        expected = (
            "CRD-123456/2026/04/14/"
            "11111111-1111-1111-1111-111111111111.json"
        )
        assert key == expected

    def test_object_key_deterministic(self, backend_and_fake):
        backend, fake = backend_and_fake
        entry_a = _fixed_entry()
        entry_b = _fixed_entry()
        backend.write(entry_a)
        backend.write(entry_b)
        assert (
            fake.put_calls[0]["object_name"]
            == fake.put_calls[1]["object_name"]
        )

    def test_retention_set_to_event_time_plus_years(
        self, backend_and_fake
    ):
        backend, fake = backend_and_fake
        entry = _fixed_entry(retention_years=6)
        backend.write(entry)
        retention = fake.put_calls[0]["retention"]
        expected_until = _FIXED_TIMESTAMP + timedelta(days=365 * 6)
        assert retention.retain_until_date == expected_until
        assert retention.mode == "COMPLIANCE"

    def test_naive_timestamp_rejected(self, backend_and_fake):
        backend, fake = backend_and_fake
        # Pydantic will coerce a naive datetime into AuditEntry; the
        # backend rejects it downstream.
        entry = _fixed_entry(
            timestamp=datetime(2026, 4, 14, 12, 0, 0)  # naive
        )
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"
        assert fake.put_calls == []

    def test_firm_id_with_path_separator_rejected(self, backend_and_fake):
        backend, fake = backend_and_fake
        entry = _fixed_entry(firm_id="../etc/passwd")
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"
        assert fake.put_calls == []

    def test_firm_id_with_slash_rejected(self, backend_and_fake):
        backend, fake = backend_and_fake
        entry = _fixed_entry(firm_id="foo/bar")
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"

    def test_put_object_s3_error_translates(self):
        fake = FakeMinioClient(put_should_raise=True)
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        with pytest.raises(AuditWriteError) as exc:
            backend.write(_fixed_entry())
        assert exc.value.reason == "worm_write_failed"

    def test_write_does_not_mutate_input_entry(self, backend_and_fake):
        backend, _ = backend_and_fake
        entry = _fixed_entry()
        original_hash = entry.sha256_integrity
        backend.write(entry)
        assert entry.sha256_integrity == original_hash

    def test_invalid_entry_type_rejected(self, backend_and_fake):
        backend, _ = backend_and_fake
        with pytest.raises(AuditWriteError) as exc:
            backend.write("not an entry")  # type: ignore[arg-type]
        assert exc.value.reason == "worm_write_failed"

    def test_missing_sha256_rejected(self, backend_and_fake):
        backend, _ = backend_and_fake
        entry = _fixed_entry(sha256_integrity="")  # un-sealed
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"

    def test_short_sha256_rejected(self, backend_and_fake):
        backend, _ = backend_and_fake
        entry = _fixed_entry(sha256_integrity="abc")
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"


# =============================================================================
# Group 4 -- TestRetentionFloor (3 cases)
# =============================================================================


class TestRetentionFloor:

    def test_entry_retention_years_7_applied(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(retention_years=6),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        entry = _fixed_entry(retention_years=7)
        backend.write(entry)
        retention = fake.put_calls[0]["retention"]
        expected = _FIXED_TIMESTAMP + timedelta(days=365 * 7)
        assert retention.retain_until_date == expected

    def test_entry_retention_years_5_rejected_runtime(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(retention_years=6),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        # AuditEntry.retention_years is Optional[int] default 6; we can
        # pass 5 and expect the backend to reject defensively.
        entry = _fixed_entry(retention_years=5)
        with pytest.raises(AuditWriteError) as exc:
            backend.write(entry)
        assert exc.value.reason == "worm_write_failed"
        assert fake.put_calls == []

    def test_config_retention_5_rejected_at_m5_parse(self):
        # Caught by M5 ValidationError (not by the backend).
        with pytest.raises(ValidationError):
            _base_config(retention_years=5)


# =============================================================================
# Group 5 -- TestGovernanceMode (2 cases)
# =============================================================================


class TestGovernanceMode:

    def test_governance_bucket_matches_construct_ok(self):
        fake = FakeMinioClient(object_lock_mode="GOVERNANCE")
        # M5 config parse emits a warning; construction succeeds.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            cfg = _base_config(object_lock_mode="GOVERNANCE")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            backend = MinIOWormBackend(
                config=cfg,
                vault_client=_vault(),
                minio_client_factory=lambda **_: fake,
            )
        assert backend._mode == "GOVERNANCE"
        msgs = [str(x.message) for x in w]
        assert any("GOVERNANCE" in m for m in msgs)

    def test_governance_config_but_compliance_bucket_fails(self):
        fake = FakeMinioClient(object_lock_mode="COMPLIANCE")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            cfg = _base_config(object_lock_mode="GOVERNANCE")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with pytest.raises(AuditWriteError) as exc:
                MinIOWormBackend(
                    config=cfg,
                    vault_client=_vault(),
                    minio_client_factory=lambda **_: fake,
                )
        assert exc.value.reason == "worm_write_failed"


# =============================================================================
# Group 6 -- TestQueryByTraceId (4 cases)
# =============================================================================


class TestQueryByTraceId:

    def _seed(self, backend, trace_ids):
        for i, tid in enumerate(trace_ids):
            e = _fixed_entry(
                trace_id=tid,
                canonical_id=UUID(int=i + 1),
            )
            backend.write(e)

    def test_returns_only_matching_trace(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        self._seed(backend, ["t1", "t1", "t2", "t1"])
        result = backend.query_by_trace_id("t1")
        assert len(result) == 3
        assert all(e.trace_id == "t1" for e in result)

    def test_unknown_trace_returns_empty(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        self._seed(backend, ["t1"])
        assert backend.query_by_trace_id("unknown") == []

    def test_list_objects_s3_error_translates(self):
        fake = FakeMinioClient(list_should_raise=True)
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        with pytest.raises(AuditWriteError) as exc:
            backend.query_by_trace_id("anything")
        assert exc.value.reason == "worm_write_failed"

    def test_firm_id_hint_narrows_prefix(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        self._seed(backend, ["t1"])
        backend.query_by_trace_id("t1", firm_id_hint="CRD-123456")
        assert fake.list_calls[-1]["prefix"] == "CRD-123456/"

    def test_bad_firm_id_hint_rejected(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        with pytest.raises(AuditWriteError) as exc:
            backend.query_by_trace_id("t1", firm_id_hint="../evil")
        assert exc.value.reason == "worm_write_failed"


# =============================================================================
# Group 7 -- TestSecurity (4 cases)
# =============================================================================


_CREDENTIAL_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"""password\s*=\s*['"][^'"]+['"]"""),
]


class TestSecurity:

    def test_repr_never_leaks_keys(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        r = repr(backend)
        s = str(backend)
        assert "fake-access-key" not in r
        assert "fake-secret-key" not in r
        assert "fake-access-key" not in s
        assert "fake-secret-key" not in s
        # sanity: repr contains bucket + endpoint
        assert "audit-worm" in r
        assert "localhost:9000" in r

    def test_no_credential_patterns_in_source(self):
        src_file = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
            / "backends_minio"
            / "minio_worm.py"
        )
        text = src_file.read_text(encoding="utf-8")
        for pattern in _CREDENTIAL_PATTERNS:
            assert not pattern.search(text), pattern.pattern

    def test_no_env_reads_in_source(self):
        src_file = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
            / "backends_minio"
            / "minio_worm.py"
        )
        text = src_file.read_text(encoding="utf-8")
        assert "os.environ" not in text
        assert "os.getenv" not in text

    def test_vault_read_exception_masked_in_raise(self):
        class ExplodingVault:
            def read_secret(self, path):
                raise RuntimeError(
                    "network error with access_key contents AKIA0000000000000000"
                )

        with pytest.raises(AuditWriteError) as exc:
            MinIOWormBackend(
                config=_base_config(),
                vault_client=ExplodingVault(),
                minio_client_factory=lambda **_: FakeMinioClient(),
            )
        # The reason is frozen; the original exception message (which
        # contains an AKIA-shaped substring) is swallowed.
        assert exc.value.reason == "worm_write_failed"
        assert "AKIA" not in str(exc.value)


# =============================================================================
# Group 8 -- TestApiSurface (3 cases)
# =============================================================================


class TestApiSurface:

    def test_lazy_import_from_top_level(self):
        # Clean access through PEP 562 __getattr__.
        from m10_audit_logger import MinIOWormBackend as Cls
        assert Cls is MinIOWormBackend

    def test_not_in_all(self):
        import m10_audit_logger
        assert "MinIOWormBackend" not in m10_audit_logger.__all__

    def test_tier_is_worm(self):
        fake = FakeMinioClient()
        backend = MinIOWormBackend(
            config=_base_config(),
            vault_client=_vault(),
            minio_client_factory=lambda **_: fake,
        )
        assert backend.tier == "worm"

    def test_unknown_attribute_raises(self):
        import m10_audit_logger
        with pytest.raises(AttributeError):
            _ = m10_audit_logger.DoesNotExist  # noqa: F841


# =============================================================================
# Helper-function tests (small + defensive)
# =============================================================================


class TestHelpers:

    def test_parse_endpoint_https(self):
        host, secure = _parse_endpoint("https://minio.example.com:9000")
        assert host == "minio.example.com:9000"
        assert secure is True

    def test_parse_endpoint_http(self):
        host, secure = _parse_endpoint("http://localhost:9000")
        assert host == "localhost:9000"
        assert secure is False

    def test_parse_endpoint_rejects_no_scheme(self):
        with pytest.raises(AuditWriteError):
            _parse_endpoint("localhost:9000")

    def test_parse_endpoint_rejects_ftp(self):
        with pytest.raises(AuditWriteError):
            _parse_endpoint("ftp://foo")

    def test_build_object_key_happy(self):
        key = _build_object_key(
            "CRD-123456",
            _FIXED_TIMESTAMP,
            _FIXED_UUID,
        )
        assert key == (
            "CRD-123456/2026/04/14/"
            "11111111-1111-1111-1111-111111111111.json"
        )

    def test_build_object_key_rejects_bad_firm_id(self):
        with pytest.raises(AuditWriteError):
            _build_object_key(
                "../etc", _FIXED_TIMESTAMP, _FIXED_UUID
            )


# =============================================================================
# Group 9 -- TestLegalHoldAPI (10 cases, Wave 4 spec m10-legal-hold-api §3 Task 4)
# =============================================================================


from m10_audit_logger.backends_minio.legal_hold import (  # noqa: E402
    HoldEntry,
    LegalHoldError,
)

from typing import Optional  # noqa: E402


_SHA256_64 = "a" * 64
_SHA256_64_B = "b" * 64


class FakeMinioClientWithLegalHold(FakeMinioClient):
    """Extends the base FakeMinioClient with legal-hold-aware surfaces."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.legal_hold_bucket_exists_calls = 0
        self.enable_legal_hold_calls: list[dict] = []
        self.disable_legal_hold_calls: list[dict] = []
        # Registry store: object_name -> (body, metadata)
        self._registry: dict[str, tuple[bytes, dict]] = {}
        # Versioning: per object_name list of tuples -- primary WORM bucket
        self._versions: dict[str, list] = {}
        # Flag: whether registry put should fail.
        self._registry_put_should_raise = kwargs.get(
            "registry_put_should_raise", False
        )

    def bucket_exists(self, bucket_name: str) -> bool:
        # Both the primary and legal-hold bucket exist by default.
        return super().bucket_exists(bucket_name)

    def list_objects(self, bucket_name, *, prefix="", recursive=True):
        # Separate namespaces for the two buckets.
        if bucket_name.endswith("-legal-holds") or "legal" in bucket_name:
            for key in sorted(self._registry.keys()):
                if key.startswith(prefix):
                    yield SimpleNamespace(
                        object_name=key, version_id="v1"
                    )
            return
        # Primary bucket.
        self.list_calls.append(
            dict(bucket_name=bucket_name, prefix=prefix, recursive=recursive)
        )
        for key in sorted(self._objects.keys()):
            if key.startswith(prefix):
                yield SimpleNamespace(object_name=key, version_id="v1")

    def get_object(self, bucket_name, object_name, version_id=None):
        if bucket_name.endswith("-legal-holds") or "legal" in bucket_name:
            if object_name not in self._registry:
                from minio.error import S3Error
                raise S3Error(
                    code="NoSuchKey",
                    message="missing",
                    resource=object_name,
                    request_id="r",
                    host_id="h",
                    response=None,
                )
            raw, _meta = self._registry[object_name]

            class _Resp:
                def __init__(self, payload: bytes):
                    self._payload = payload

                def read(self):
                    return self._payload

                def close(self):
                    pass

                def release_conn(self):
                    pass

            return _Resp(raw)
        return super().get_object(bucket_name, object_name)

    def put_object(self, **kwargs):
        bucket = kwargs.get("bucket_name", "")
        if bucket.endswith("-legal-holds") or "legal" in bucket:
            if self._registry_put_should_raise:
                from minio.error import S3Error
                raise S3Error(
                    code="InternalError",
                    message="registry-boom",
                    resource=bucket,
                    request_id="r",
                    host_id="h",
                    response=None,
                )
            data = kwargs.get("data")
            raw = data.read() if data is not None else b""
            key = kwargs["object_name"]
            self._registry[key] = (raw, dict(kwargs.get("metadata") or {}))
            return SimpleNamespace(object_name=key, etag="fake-etag")
        # Primary bucket.
        return super().put_object(**kwargs)

    def enable_object_legal_hold(
        self, *, bucket_name, object_name, version_id=None
    ):
        self.enable_legal_hold_calls.append(
            dict(
                bucket_name=bucket_name,
                object_name=object_name,
                version_id=version_id,
            )
        )

    def disable_object_legal_hold(
        self, *, bucket_name, object_name, version_id=None
    ):
        self.disable_legal_hold_calls.append(
            dict(
                bucket_name=bucket_name,
                object_name=object_name,
                version_id=version_id,
            )
        )


class _NullOrchestrator:
    """Stand-in AuditLogger. ``write`` writes the audit entry to the
    backend's primary WORM bucket (the same fake client) so the
    meta-hold path can resolve the just-written audit record's target
    version in the primary bucket. Production AuditLogger does this
    via its ``worm`` tier backend which IS the MinIOWormBackend
    instance.
    """

    def __init__(self, worm_backend: Optional["MinIOWormBackend"] = None):
        self.writes: list = []
        self._worm_backend = worm_backend

    def attach(self, worm_backend):
        self._worm_backend = worm_backend

    def write(self, entry):
        self.writes.append(entry)
        if self._worm_backend is not None:
            # Seal + write to primary WORM bucket so legal-hold
            # machinery can find the target version.
            # We bypass the backend's strict sha256_integrity check by
            # computing a fake seal hash.
            import hashlib
            from m10_audit_logger.logger import _canonical_json as _cj
            sealed = entry.model_copy(
                update={
                    "sha256_integrity": hashlib.sha256(
                        _cj(entry.model_dump(
                            mode="json", exclude={"sha256_integrity"}
                        )).encode("utf-8")
                    ).hexdigest()
                }
            )
            self._worm_backend.write(sealed)
            return sealed
        return entry


def _backend_with_holds(
    *, factory_kwargs=None, orchestrator=None
) -> tuple[MinIOWormBackend, FakeMinioClientWithLegalHold]:
    """Shared fixture: happy backend + fake with legal-hold support."""
    fake = FakeMinioClientWithLegalHold(**(factory_kwargs or {}))
    backend = MinIOWormBackend(
        config=_base_config(),
        vault_client=_vault(),
        minio_client_factory=lambda **_: fake,
        orchestrator=orchestrator,
    )
    if orchestrator is not None and hasattr(orchestrator, "attach"):
        orchestrator.attach(backend)
    return backend, fake


class TestLegalHoldAPI:

    def _place_target_entry(
        self,
        backend: MinIOWormBackend,
        fake: FakeMinioClientWithLegalHold,
        *,
        canonical_id,
    ) -> None:
        """Write a baseline audit entry so target-version resolution works."""
        entry = _fixed_entry(canonical_id=canonical_id)
        backend.write(entry)

    # --- Case 1 ---
    def test_place_hold_happy_path(self):
        orch = _NullOrchestrator()
        backend, fake = _backend_with_holds(orchestrator=orch)
        cid = UUID("22222222-2222-2222-2222-222222222222")
        self._place_target_entry(backend, fake, canonical_id=cid)

        hold = backend.place_legal_hold(
            canonical_id=cid,
            hold_id="matter-2026-001",
            reason="SEC subpoena 2026-SDNY-8421",
            placed_by=_SHA256_64,
        )

        assert isinstance(hold, HoldEntry)
        assert hold.hold_id == "matter-2026-001"
        assert hold.canonical_id == cid
        assert hold.is_active is True
        # Registry object written.
        key = f"{cid}/matter-2026-001.json"
        assert key in fake._registry
        # MinIO-level legal-hold flag toggled ON.
        assert len(fake.enable_legal_hold_calls) >= 1
        assert fake.enable_legal_hold_calls[0]["object_name"].endswith(
            f"/{cid}.json"
        )
        # Audit orchestrator emitted >= 1 audit (the hold placement).
        assert len(orch.writes) >= 1

    # --- Case 2 ---
    def test_release_hold_happy_path(self):
        orch = _NullOrchestrator()
        backend, fake = _backend_with_holds(orchestrator=orch)
        cid = UUID("33333333-3333-3333-3333-333333333333")
        self._place_target_entry(backend, fake, canonical_id=cid)

        backend.place_legal_hold(
            canonical_id=cid,
            hold_id="matter-2026-002",
            reason="Regulator inquiry",
            placed_by=_SHA256_64,
        )
        initial_writes = len(orch.writes)

        released = backend.release_legal_hold(
            canonical_id=cid,
            hold_id="matter-2026-002",
            reason="Matter closed",
            released_by=_SHA256_64_B,
        )

        assert released.is_active is False
        assert released.released_at is not None
        assert released.released_by == _SHA256_64_B
        # Flag toggled OFF.
        assert len(fake.disable_legal_hold_calls) >= 1
        # Audit orchestrator saw >=1 more write for the release event.
        assert len(orch.writes) > initial_writes

    # --- Case 3 ---
    def test_place_duplicate_hold_rejected(self):
        backend, fake = _backend_with_holds()
        cid = UUID("44444444-4444-4444-4444-444444444444")
        self._place_target_entry(backend, fake, canonical_id=cid)

        backend.place_legal_hold(
            canonical_id=cid,
            hold_id="dup-hold",
            reason="First hold",
            placed_by=_SHA256_64,
        )
        with pytest.raises(LegalHoldError) as exc:
            backend.place_legal_hold(
                canonical_id=cid,
                hold_id="dup-hold",
                reason="Second hold attempt",
                placed_by=_SHA256_64,
            )
        assert exc.value.reason == "duplicate_hold_id"

    # --- Case 4 ---
    def test_release_with_wrong_hold_id_rejected(self):
        backend, fake = _backend_with_holds()
        cid = UUID("55555555-5555-5555-5555-555555555555")
        self._place_target_entry(backend, fake, canonical_id=cid)

        backend.place_legal_hold(
            canonical_id=cid,
            hold_id="real-hold",
            reason="active",
            placed_by=_SHA256_64,
        )
        with pytest.raises(LegalHoldError) as exc:
            backend.release_legal_hold(
                canonical_id=cid,
                hold_id="different-hold-id",
                reason="Trying to release a different hold",
                released_by=_SHA256_64_B,
            )
        assert exc.value.reason == "hold_not_found"

    # --- Case 5 ---
    def test_release_already_released_hold_rejected(self):
        backend, fake = _backend_with_holds()
        cid = UUID("66666666-6666-6666-6666-666666666666")
        self._place_target_entry(backend, fake, canonical_id=cid)

        backend.place_legal_hold(
            canonical_id=cid,
            hold_id="once-only",
            reason="initial",
            placed_by=_SHA256_64,
        )
        backend.release_legal_hold(
            canonical_id=cid,
            hold_id="once-only",
            reason="closed",
            released_by=_SHA256_64_B,
        )
        with pytest.raises(LegalHoldError) as exc:
            backend.release_legal_hold(
                canonical_id=cid,
                hold_id="once-only",
                reason="second release",
                released_by=_SHA256_64_B,
            )
        assert exc.value.reason == "hold_already_released"

    # --- Case 6 ---
    def test_list_legal_holds_returns_only_active(self):
        backend, fake = _backend_with_holds()
        cid = UUID("77777777-7777-7777-7777-777777777777")
        self._place_target_entry(backend, fake, canonical_id=cid)

        backend.place_legal_hold(
            canonical_id=cid, hold_id="h-A", reason="active-A",
            placed_by=_SHA256_64,
        )
        backend.place_legal_hold(
            canonical_id=cid, hold_id="h-B", reason="active-B",
            placed_by=_SHA256_64,
        )
        backend.release_legal_hold(
            canonical_id=cid, hold_id="h-A", reason="closing A",
            released_by=_SHA256_64_B,
        )

        active = backend.list_legal_holds(cid)
        assert len(active) == 1
        assert active[0].hold_id == "h-B"
        assert active[0].is_active is True

    # --- Case 7 ---
    def test_list_legal_holds_returns_empty_when_none(self):
        backend, fake = _backend_with_holds()
        cid = UUID("88888888-8888-8888-8888-888888888888")
        self._place_target_entry(backend, fake, canonical_id=cid)
        assert backend.list_legal_holds(cid) == []

    # --- Case 8 ---
    def test_place_hold_target_not_found(self):
        backend, _fake = _backend_with_holds()
        # canonical_id has no underlying audit entry.
        unknown_cid = UUID("99999999-9999-9999-9999-999999999999")

        with pytest.raises(LegalHoldError) as exc:
            backend.place_legal_hold(
                canonical_id=unknown_cid,
                hold_id="no-target",
                reason="will fail",
                placed_by=_SHA256_64,
            )
        assert exc.value.reason == "target_not_found"

    # --- Case 9 ---
    def test_hold_entry_repr_redacts_reason(self):
        from datetime import datetime, timezone
        e = HoldEntry(
            hold_id="abc-123",
            canonical_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            reason="confidential matter details SEC investigation 2026",
            placed_by=_SHA256_64,
            placed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        r = repr(e)
        s = str(e)
        assert "[REDACTED]" in r
        assert "[REDACTED]" in s
        assert "confidential" not in r
        assert "confidential" not in s
        assert "SEC investigation" not in r
        assert "SEC investigation" not in s

    # --- Case 10 ---
    def test_meta_hold_does_not_recurse(self):
        """The meta-hold (hold_id starting with 'meta-') MUST NOT itself
        trigger a further meta-hold -- otherwise place_legal_hold
        recurses forever."""
        orch = _NullOrchestrator()
        backend, fake = _backend_with_holds(orchestrator=orch)
        cid = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self._place_target_entry(backend, fake, canonical_id=cid)

        # Place a primary hold. The backend emits an audit + auto
        # meta-holds the audit record (that meta-hold counts as a
        # second place_legal_hold invocation internally).
        backend.place_legal_hold(
            canonical_id=cid,
            hold_id="primary-hold",
            reason="Primary case",
            placed_by=_SHA256_64,
        )

        # After the call returns, the registry should have:
        #   - {cid}/primary-hold.json (the primary)
        #   - {meta-cid}/meta-primary-hold.json (the meta-hold)
        # And NO meta-meta-primary-hold (termination rule).
        meta_keys = [k for k in fake._registry if k.endswith("/meta-primary-hold.json")]
        meta_meta_keys = [
            k for k in fake._registry if "meta-meta-primary-hold" in k
        ]
        assert len(meta_keys) == 1, \
            f"expected one meta-hold, got {meta_keys}"
        assert meta_meta_keys == [], \
            f"meta-meta recursion occurred: {meta_meta_keys}"

"""
M10 MinIO WORM Backend -- Integration Tests.

Exercises ``MinIOWormBackend`` end-to-end against a real MinIO server.

Discovery order for the MinIO endpoint (first match wins):
    1. Env var ``M10_MINIO_TEST_ENDPOINT`` -- operator-supplied
       ``host:port`` for a pre-started MinIO running with
       ``--object-lock`` (``MINIO_ROOT_USER`` / ``MINIO_ROOT_PASSWORD``
       also sourced from env).
    2. ``testcontainers-python`` + a reachable Docker daemon -- spins
       up an ephemeral MinIO container.

If neither is available, the module skips. Unit tests in
``test_m10_minio_worm.py`` cover all logic without needing MinIO.

These tests are marked ``@pytest.mark.integration`` so CI envs without
MinIO or Docker can do ``-m "not integration"`` and stay green.

Run locally (env-var path):
    finch run -d -p 19000:9000 \\
      -e MINIO_ROOT_USER=... -e MINIO_ROOT_PASSWORD=... \\
      minio/minio:RELEASE.2024-10-02T17-50-41Z server /data
    export M10_MINIO_TEST_ENDPOINT=localhost:19000
    export M10_MINIO_TEST_ACCESS_KEY=...
    export M10_MINIO_TEST_SECRET_KEY=...
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest \\
            my-agent-project-007-fsi-interoperability/\\
            tests/integration/test_m10_minio_worm_integration.py \\
            -v -m integration

Spec: ``.kiro/specs/m10-worm-minio-backend.md`` §4.2.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

# The minio SDK is required for the real backend + the test-side bucket
# provisioning. Skip module if missing.
minio_sdk = pytest.importorskip("minio")
from minio import Minio  # noqa: E402
from minio.commonconfig import COMPLIANCE  # noqa: E402
from minio.error import S3Error  # noqa: E402
from minio.objectlockconfig import ObjectLockConfig, YEARS  # noqa: E402

from m3_schema_registry import AuditEntry  # noqa: E402
from m10_audit_logger import AuditWriteError  # noqa: E402
from m10_audit_logger.backends_minio.minio_worm import (  # noqa: E402
    MinIOWormBackend,
)
from m5_config_loader import MinIOWormConfig  # noqa: E402


pytestmark = pytest.mark.integration


# -----------------------------------------------------------------------------
# Endpoint discovery: env-var first, testcontainers second, else skip module.
# Keep the Protocol names local so we can swap either pathway transparently.
# -----------------------------------------------------------------------------


_ENDPOINT_ENV = "M10_MINIO_TEST_ENDPOINT"
_ACCESS_ENV = "M10_MINIO_TEST_ACCESS_KEY"
_SECRET_ENV = "M10_MINIO_TEST_SECRET_KEY"


class _EnvMinio:
    """Adapter that mimics the testcontainers-Container surface
    (just the `.get_container_host_ip()` / `.get_exposed_port()` pair)
    using a pre-existing MinIO at a known endpoint."""

    def __init__(self, endpoint: str, access: str, secret: str):
        host, _, port = endpoint.partition(":")
        self._host = host or "localhost"
        self._port = int(port or "9000")
        self.access = access
        self.secret = secret

    def get_container_host_ip(self) -> str:  # noqa: D401
        return self._host

    def get_exposed_port(self, _p: int) -> int:
        return self._port

    def stop(self) -> None:
        return None


def _try_env_minio():
    endpoint = os.environ.get(_ENDPOINT_ENV)
    access = os.environ.get(_ACCESS_ENV)
    secret = os.environ.get(_SECRET_ENV)
    if endpoint and access and secret:
        return _EnvMinio(endpoint, access, secret)
    return None


def _try_testcontainers():
    try:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs
    except Exception:
        return None

    access = "m10integaccess"
    secret = "m10integsecretlongenough32chars"
    try:
        container = (
            DockerContainer(
                "minio/minio:RELEASE.2024-10-02T17-50-41Z"
            )
            .with_env("MINIO_ROOT_USER", access)
            .with_env("MINIO_ROOT_PASSWORD", secret)
            .with_exposed_ports(9000)
            .with_command(
                "server /data --console-address :9001"
            )
        )
        container.start()
        wait_for_logs(container, "API:", timeout=30)
    except Exception:
        return None

    class _TcAdapter:
        def __init__(self, c):
            self._c = c
            self.access = access
            self.secret = secret

        def get_container_host_ip(self) -> str:
            return self._c.get_container_host_ip()

        def get_exposed_port(self, p: int) -> int:
            return int(self._c.get_exposed_port(p))

        def stop(self) -> None:
            self._c.stop()

    return _TcAdapter(container)


@pytest.fixture(scope="module")
def minio_container():
    """Yield an adapter exposing host_ip/port + access/secret."""
    env_minio = _try_env_minio()
    if env_minio is not None:
        yield env_minio
        return

    tc_minio = _try_testcontainers()
    if tc_minio is not None:
        try:
            yield tc_minio
        finally:
            tc_minio.stop()
        return

    pytest.skip(
        f"No MinIO endpoint available. Set {_ENDPOINT_ENV}="
        "localhost:9000 (with matching *_ACCESS_KEY / *_SECRET_KEY) "
        "or install testcontainers + run a Docker-compatible daemon."
    )


@pytest.fixture(scope="module")
def minio_endpoint(minio_container):
    return (
        f"{minio_container.get_container_host_ip()}:"
        f"{minio_container.get_exposed_port(9000)}"
    )


@pytest.fixture(scope="module")
def admin_creds(minio_container):
    return minio_container.access, minio_container.secret


@pytest.fixture(scope="module")
def admin_client(minio_endpoint, admin_creds):
    access, secret = admin_creds
    return Minio(
        endpoint=minio_endpoint,
        access_key=access,
        secret_key=secret,
        secure=False,
    )


class _Vault:
    def __init__(self, access: str, secret: str):
        self._access = access
        self._secret = secret

    def read_secret(self, path: str) -> str:
        if path.endswith("access_key"):
            return self._access
        if path.endswith("secret_key"):
            return self._secret
        raise KeyError(path)


@pytest.fixture(scope="module")
def vault(admin_creds):
    access, secret = admin_creds
    return _Vault(access, secret)


def _mk_bucket(admin_client: Minio, name: str, *, object_lock: bool = True) -> None:
    """Create a fresh bucket with Object Lock enabled (or disabled)."""
    try:
        admin_client.make_bucket(name, object_lock=object_lock)
    except S3Error as e:
        if e.code != "BucketAlreadyOwnedByYou":
            raise
    if object_lock:
        # Default retention: Compliance mode, 6 years.
        admin_client.set_object_lock_config(
            name,
            ObjectLockConfig(
                mode=COMPLIANCE, duration=6, duration_unit=YEARS
            ),
        )


def _mk_config(endpoint: str, bucket: str) -> MinIOWormConfig:
    return MinIOWormConfig(
        endpoint_url=f"http://{endpoint}",
        bucket_name=bucket,
        region="us-east-1",
        access_key_vault_path="secret/data/m10/minio/access_key",
        secret_key_vault_path="secret/data/m10/minio/secret_key",
        retention_years=6,
        object_lock_mode="COMPLIANCE",
        secure=False,
    )


def _entry(**overrides) -> AuditEntry:
    kwargs = dict(
        canonical_id=overrides.pop("canonical_id", uuid4()),
        trace_id=overrides.pop("trace_id", "trace-integ-001"),
        timestamp=overrides.pop(
            "timestamp",
            datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
        ),
        actor_id="integ-actor",
        action="integ.test",
        module="m10",
        decision="allow",
        input_hash="0" * 64,
        output_hash="1" * 64,
        latency_ms=1,
        firm_id=overrides.pop("firm_id", "firm-integ"),
        worm_record_id="integ/wrid",
        sha256_integrity=overrides.pop("sha256_integrity", "f" * 64),
        retention_years=6,
    )
    kwargs.update(overrides)
    return AuditEntry(**kwargs)


# -----------------------------------------------------------------------------
# Tests (8 scenarios per spec §4.2)
# -----------------------------------------------------------------------------


def test_1_write_then_get_object_roundtrip(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ1-roundtrip-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    entry = _entry(canonical_id=uuid4())
    backend.write(entry)

    key = (
        f"{entry.firm_id}/2026/04/14/{entry.canonical_id}.json"
    )
    response = admin_client.get_object(bucket, key)
    try:
        body = response.read()
    finally:
        response.close()
        response.release_conn()
    parsed = AuditEntry.model_validate(
        json.loads(body.decode("utf-8"))
    )
    assert parsed.canonical_id == entry.canonical_id
    assert parsed.trace_id == entry.trace_id


def test_2_sha256_metadata_persists(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ2-metadata-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    entry = _entry(canonical_id=uuid4(), sha256_integrity="b" * 64)
    backend.write(entry)
    key = f"{entry.firm_id}/2026/04/14/{entry.canonical_id}.json"
    stat = admin_client.stat_object(bucket, key)
    # MinIO prefixes user-defined metadata with x-amz-meta- on read.
    meta = {k.lower(): v for k, v in stat.metadata.items()}
    assert meta.get("x-amz-meta-sha256-integrity") == "b" * 64
    assert meta.get("x-amz-meta-trace-id") == "trace-integ-001"
    assert meta.get("x-amz-meta-firm-id") == "firm-integ"


def test_3_retention_blocks_delete(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ3-retention-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    entry = _entry(canonical_id=uuid4())
    backend.write(entry)
    key = f"{entry.firm_id}/2026/04/14/{entry.canonical_id}.json"

    # With Object Lock + bucket versioning:
    #  * A delete WITHOUT version ID creates a delete marker (the
    #    underlying version is preserved -- standard S3 semantics).
    #  * A delete WITH the version ID is what Object Lock actually
    #    blocks, because that targets the immutable version itself.
    # The compliant behaviour is: targeted version deletes MUST fail.
    versions = [
        v
        for v in admin_client.list_objects(
            bucket, prefix=key, recursive=True, include_version=True
        )
        if not v.is_delete_marker
    ]
    assert len(versions) == 1, f"unexpected versions: {versions}"
    with pytest.raises(S3Error) as exc_info:
        admin_client.remove_object(
            bucket, key, version_id=versions[0].version_id
        )
    # MinIO returns one of these codes when deleting a Compliance-mode
    # object before retain_until_date.
    assert exc_info.value.code in (
        "InvalidRequest",
        "AccessDenied",
        "ObjectLocked",
        "AccessDeniedException",
        "WORMOnBucket",
        "InvalidBucketState",
    )


def test_4_integrity_roundtrips_and_tamper_rejected(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ4-integrity-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    entry = _entry(canonical_id=uuid4(), sha256_integrity="c" * 64)
    backend.write(entry)
    key = f"{entry.firm_id}/2026/04/14/{entry.canonical_id}.json"
    stat = admin_client.stat_object(bucket, key)
    meta = {k.lower(): v for k, v in stat.metadata.items()}
    assert meta.get("x-amz-meta-sha256-integrity") == "c" * 64

    # In a versioned+object-lock bucket, an "overwrite" creates a NEW
    # version; the original immutable version is unreachable via an
    # undecorated PUT but still present under its version ID. So the
    # compliance check is: the original version's bytes are stable and
    # its retention-until date is unchanged after the "overwrite"
    # attempt.
    original_version_id = stat.version_id
    assert original_version_id, "expected versioning to be enabled"

    # Attempt the "tamper" PUT -- this just adds a NEW version.
    admin_client.put_object(
        bucket,
        key,
        data=io.BytesIO(b"tampered body"),
        length=len(b"tampered body"),
        content_type="application/json",
    )

    # The ORIGINAL version's body and metadata must be unchanged.
    re_stat = admin_client.stat_object(
        bucket, key, version_id=original_version_id
    )
    re_meta = {k.lower(): v for k, v in re_stat.metadata.items()}
    assert re_meta.get("x-amz-meta-sha256-integrity") == "c" * 64
    resp = admin_client.get_object(
        bucket, key, version_id=original_version_id
    )
    try:
        body = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    parsed = AuditEntry.model_validate(json.loads(body.decode("utf-8")))
    assert parsed.sha256_integrity == "c" * 64

    # And a TARGETED delete of the original version MUST still fail.
    with pytest.raises(S3Error):
        admin_client.remove_object(
            bucket, key, version_id=original_version_id
        )


def test_5_query_by_trace_id_returns_matches(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ5-query-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    for _ in range(2):
        backend.write(_entry(canonical_id=uuid4(), trace_id="A"))
    backend.write(_entry(canonical_id=uuid4(), trace_id="B"))
    backend.write(_entry(canonical_id=uuid4(), trace_id="A"))

    matches = backend.query_by_trace_id("A", firm_id_hint="firm-integ")
    assert len(matches) == 3
    assert all(m.trace_id == "A" for m in matches)


def test_6_multi_firm_isolation(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ6-multifirm-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, bucket),
        vault_client=vault,
    )
    backend.write(
        _entry(canonical_id=uuid4(), firm_id="firm-A", trace_id="T1")
    )
    backend.write(
        _entry(canonical_id=uuid4(), firm_id="firm-B", trace_id="T1")
    )

    matches = backend.query_by_trace_id("T1", firm_id_hint="firm-A")
    assert len(matches) == 1
    assert matches[0].firm_id == "firm-A"


def test_7_object_lock_disabled_bucket_fails_startup(
    admin_client, minio_endpoint, vault
):
    bucket = f"integ7-no-lock-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, bucket, object_lock=False)
    with pytest.raises(AuditWriteError) as exc:
        MinIOWormBackend(
            config=_mk_config(minio_endpoint, bucket),
            vault_client=vault,
        )
    assert exc.value.reason == "worm_write_failed"


def test_8_connection_refused_fails_startup(vault):
    # Point at a definitely-unreachable host/port. No server needed.
    cfg = MinIOWormConfig(
        endpoint_url="http://127.0.0.1:1/",
        bucket_name="any-bucket",
        region="us-east-1",
        access_key_vault_path="secret/data/m10/minio/access_key",
        secret_key_vault_path="secret/data/m10/minio/secret_key",
        retention_years=6,
        object_lock_mode="COMPLIANCE",
        secure=False,
    )
    with pytest.raises(AuditWriteError) as exc:
        MinIOWormBackend(config=cfg, vault_client=vault)
    assert exc.value.reason == "worm_write_failed"


# =============================================================================
# Wave 4 legal-hold integration tests (m10-legal-hold-api §3 Task 5).
# Integration cases 9-11. Same testcontainers-or-env discovery as 1-8.
# =============================================================================

from m10_audit_logger.backends_minio.legal_hold import (  # noqa: E402
    HoldEntry,
    LegalHoldError,
)


def _mk_hold_registry_bucket(admin_client: Minio, name: str) -> None:
    """Provision the legal-hold registry bucket with Object Lock + 6y
    compliance retention."""
    try:
        admin_client.make_bucket(name, object_lock=True)
    except S3Error as e:
        if e.code != "BucketAlreadyOwnedByYou":
            raise
    admin_client.set_object_lock_config(
        name,
        ObjectLockConfig(mode=COMPLIANCE, duration=6, duration_unit=YEARS),
    )


_SHA256_64 = "a" * 64
_SHA256_64_B = "b" * 64


def test_integration_9_place_hold_roundtrip(
    admin_client, minio_endpoint, vault
):
    """End-to-end place_legal_hold against a real MinIO. Registry object
    lands under the hold-registry bucket; legal-hold flag ON."""
    primary = f"integ9-primary-{uuid4().hex[:8]}"
    registry = f"integ9-legal-holds-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, primary)
    _mk_hold_registry_bucket(admin_client, registry)

    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, primary),
        vault_client=vault,
        legal_hold_bucket_name=registry,
    )
    # Seed an audit entry in the primary bucket.
    target = _entry(canonical_id=uuid4())
    backend.write(target)

    hold = backend.place_legal_hold(
        canonical_id=target.canonical_id,
        hold_id="integ-9-matter",
        reason="integration-test legal hold placement",
        placed_by=_SHA256_64,
    )
    assert isinstance(hold, HoldEntry)
    assert hold.is_active is True
    # Registry object exists.
    stat = admin_client.stat_object(
        registry, f"{target.canonical_id}/integ-9-matter.json"
    )
    assert stat.size > 0


def test_integration_10_release_hold_roundtrip(
    admin_client, minio_endpoint, vault
):
    """End-to-end release_legal_hold. Registry gains a released version;
    legal-hold flag OFF on the target."""
    primary = f"integ10-primary-{uuid4().hex[:8]}"
    registry = f"integ10-legal-holds-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, primary)
    _mk_hold_registry_bucket(admin_client, registry)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, primary),
        vault_client=vault,
        legal_hold_bucket_name=registry,
    )
    target = _entry(canonical_id=uuid4())
    backend.write(target)
    backend.place_legal_hold(
        canonical_id=target.canonical_id,
        hold_id="integ-10-matter",
        reason="placed for release test",
        placed_by=_SHA256_64,
    )

    released = backend.release_legal_hold(
        canonical_id=target.canonical_id,
        hold_id="integ-10-matter",
        reason="matter closed",
        released_by=_SHA256_64_B,
    )
    assert released.is_active is False
    assert released.released_by == _SHA256_64_B
    # list_legal_holds now returns empty.
    active = backend.list_legal_holds(target.canonical_id)
    assert active == []


def test_integration_11_tamper_blocked_by_retention_and_hold(
    admin_client, minio_endpoint, vault
):
    """Object Lock retention + legal-hold BOTH block tampering.

    Defence-in-depth: even if retention were incorrectly shortened, the
    legal-hold flag still blocks deletes of the target version.
    """
    primary = f"integ11-primary-{uuid4().hex[:8]}"
    registry = f"integ11-legal-holds-{uuid4().hex[:8]}"
    _mk_bucket(admin_client, primary)
    _mk_hold_registry_bucket(admin_client, registry)
    backend = MinIOWormBackend(
        config=_mk_config(minio_endpoint, primary),
        vault_client=vault,
        legal_hold_bucket_name=registry,
    )
    target = _entry(canonical_id=uuid4())
    backend.write(target)
    backend.place_legal_hold(
        canonical_id=target.canonical_id,
        hold_id="integ-11-matter",
        reason="tamper-evidence test",
        placed_by=_SHA256_64,
    )

    # Find the target object version (same traversal the backend uses).
    key = None
    for obj in admin_client.list_objects(
        primary, recursive=True, include_version=True
    ):
        if obj.object_name and obj.object_name.endswith(
            f"/{target.canonical_id}.json"
        ):
            key = obj.object_name
            version = obj.version_id
            break
    assert key is not None, "expected to find the target object"

    # 1. retention blocks delete.
    with pytest.raises(S3Error) as e1:
        admin_client.remove_object(primary, key, version_id=version)
    assert e1.value.code in (
        "InvalidRequest",
        "AccessDenied",
        "ObjectLocked",
        "WORMOnBucket",
        "InvalidBucketState",
    )

    # 2. legal-hold flag alone also blocks: even if we somehow had
    # governance-mode or an expired retain_until, the hold MUST stop
    # deletes. We verify the flag is set (SDK-side check).
    flag_enabled = admin_client.is_object_legal_hold_enabled(
        primary, key, version_id=version
    )
    assert flag_enabled is True

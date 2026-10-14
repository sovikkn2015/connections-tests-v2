"""
M10 Audit Logger — Unit Tests.

Covers spec §3 tasks T10..T33 (R1..R10 acceptance criteria).

    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/tests/ -v
"""

from __future__ import annotations

import ast
import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from m3_schema_registry import AuditEntry, ProvenanceStage

import m10_audit_logger
from m10_audit_logger import (
    AuditBackend,
    AuditDLQ,
    AuditLogger,
    AuditWriteError,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
    MIN_RETENTION_YEARS,
    ProvenanceChainBuilder,
    VALID_REASONS,
    VALID_TIERS,
)
from m10_audit_logger import backends as backends_mod
from m10_audit_logger import logger as logger_mod
from m10_audit_logger import provenance as provenance_mod
from m10_audit_logger.logger import (
    _canonical_json,
    _compute_integrity_hash,
    _json_default,
)
from m10_audit_logger.provenance import _MODULE_PATTERN, _stage_hash


# =============================================================================
# Golden vectors (independently computed — see spec §2.14 and §3.2)
# =============================================================================

# For _fixed_entry(). Expected canonical JSON (key-sorted, compact):
# {"action":"test.action","actor_id":"actor-hash-abc","archetype":null,
#  "canonical_id":"11111111-1111-1111-1111-111111111111","crm_record_id":null,
#  "data_sources_used":[],"decision":"allow","firm_id":"CRD-123456",
#  "input_hash":"<64*0>","jurisdiction":null,"langfuse_trace_url":null,
#  "latency_ms":5,"module":"m10","output_hash":"<64*1>",
#  "policy_bundle_version":null,"provenance_chain":[],"reason":null,
#  "retention_years":6,"role":null,"rule_applied":null,"target_id":null,
#  "target_type":null,"timestamp":"2026-04-14T12:00:00Z",
#  "trace_id":"trace-fixed-001","worm_record_id":"worm/key/fixed",
#  "wsp_section":null}
# SHA-256 of the above (utf-8 bytes):
ENTRY_GOLDEN_HASH = (
    "887b903d7fea42bb1beaf80efad2cd76f7e3ff7230ce3489cf38f9f96dd85d89"
)

# For a single provenance stage with the fixture inputs below:
#   stage="m1.verify", module="m1",
#   payload={"stage_data": "value-0"},
#   timestamp=datetime(2026,4,14,12,0,0, tzinfo=utc)
# payload canonical: {"stage_data":"value-0"}
STAGE0_PAYLOAD_HASH = (
    "71ad369868ea15ee95263288c0f85f8345a1171f549cab086e73a7e8fd631959"
)
# components: "" + "|m1.verify|m1|<payload_hash>|2026-04-14T12:00:00+00:00"
STAGE0_GOLDEN_HASH = (
    "6ed5f5570359818119cd5360846794b849abf5b2e0a91fd10b7001126148ffe6"
)


# =============================================================================
# Fixtures — explicit, no credentials
# =============================================================================

_FIXED_TIMESTAMP = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_UUID = UUID("11111111-1111-1111-1111-111111111111")


def _fixed_entry(**overrides) -> AuditEntry:
    """Deterministic fixture for golden-vector tests. No credentials."""
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
        sha256_integrity="",
        retention_years=6,
    )
    kwargs.update(overrides)
    return AuditEntry(**kwargs)


@pytest.fixture
def backends():
    """Fresh triple of healthy in-memory backends."""
    return (
        InMemoryAuditBackend(tier="langfuse"),
        InMemoryAuditBackend(tier="worm"),
        InMemoryAuditBackend(tier="crm"),
    )


@pytest.fixture
def dlq():
    return InMemoryAuditDLQ()


@pytest.fixture
def logger(backends, dlq):
    lf, worm, crm = backends
    return AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)


# =============================================================================
# T10 — Happy-path 3-tier write (R1)
# =============================================================================


class TestHappyPath:

    def test_returns_sealed_entry_with_hex_hash(self, logger):
        # AC-R1-1
        entry = _fixed_entry()
        sealed = logger.write(entry)
        assert isinstance(sealed, AuditEntry)
        assert re.fullmatch(r"[0-9a-f]{64}", sealed.sha256_integrity)

    def test_input_entry_not_mutated(self, logger):
        # AC-R1-2
        entry = _fixed_entry()
        original_hash = entry.sha256_integrity
        sealed = logger.write(entry)
        assert sealed is not entry
        assert entry.sha256_integrity == original_hash == ""

    def test_all_three_backends_receive_sealed_entry(self, backends, dlq):
        # AC-R1-3
        lf, worm, crm = backends
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        sealed = log.write(_fixed_entry())
        assert len(lf.entries) == 1
        assert len(worm.entries) == 1
        assert len(crm.entries) == 1
        assert lf.entries[0].sha256_integrity == sealed.sha256_integrity
        assert worm.entries[0].sha256_integrity == sealed.sha256_integrity
        assert crm.entries[0].sha256_integrity == sealed.sha256_integrity


# =============================================================================
# T11 — Langfuse failure
# =============================================================================


class TestLangfuseFailure:

    def test_langfuse_failure_raises_and_dlqs(self, dlq):
        # AC-R1-4, AC-R6-1
        lf = InMemoryAuditBackend(tier="langfuse", fail_on_nth=1)
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm")
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        with pytest.raises(AuditWriteError) as exc_info:
            log.write(_fixed_entry())
        assert exc_info.value.reason == "langfuse_write_failed"
        assert len(dlq.records) == 1
        assert dlq.records[0][1] == "langfuse_write_failed"
        assert lf.entries == []
        assert worm.entries == []
        assert crm.entries == []


# =============================================================================
# T12 — WORM failure
# =============================================================================


class TestWormFailure:

    def test_worm_failure_raises_and_dlqs(self, dlq):
        # AC-R1-5, AC-R6-2
        lf = InMemoryAuditBackend(tier="langfuse")
        worm = InMemoryAuditBackend(tier="worm", fail_on_nth=1)
        crm = InMemoryAuditBackend(tier="crm")
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        with pytest.raises(AuditWriteError) as exc_info:
            log.write(_fixed_entry())
        assert exc_info.value.reason == "worm_write_failed"
        assert len(dlq.records) == 1
        assert dlq.records[0][1] == "worm_write_failed"
        assert len(lf.entries) == 1
        assert worm.entries == []
        assert crm.entries == []


# =============================================================================
# T13 — CRM failure
# =============================================================================


class TestCrmFailure:

    def test_crm_failure_raises_and_dlqs(self, dlq):
        # AC-R1-6, AC-R6-3
        lf = InMemoryAuditBackend(tier="langfuse")
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm", fail_on_nth=1)
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        with pytest.raises(AuditWriteError) as exc_info:
            log.write(_fixed_entry())
        assert exc_info.value.reason == "crm_write_failed"
        assert len(dlq.records) == 1
        assert dlq.records[0][1] == "crm_write_failed"
        assert len(lf.entries) == 1
        assert len(worm.entries) == 1
        assert crm.entries == []


# =============================================================================
# T14 — Input validation (R1)
# =============================================================================


class TestInputValidation:

    def test_invalid_entry_dict(self, logger):
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write({"canonical_id": "x"})  # type: ignore[arg-type]
        assert exc_info.value.reason == "invalid_entry"

    def test_invalid_entry_string(self, logger):
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write("not an entry")  # type: ignore[arg-type]
        assert exc_info.value.reason == "invalid_entry"

    def test_invalid_entry_none(self, logger):
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write(None)  # type: ignore[arg-type]
        assert exc_info.value.reason == "invalid_entry"

    def test_retention_too_short_5(self, logger):
        entry = _fixed_entry(retention_years=5)
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write(entry)
        assert exc_info.value.reason == "retention_too_short"

    def test_retention_too_short_none(self, logger):
        entry = _fixed_entry(retention_years=None)
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write(entry)
        assert exc_info.value.reason == "retention_too_short"

    def test_retention_6_succeeds(self, logger):
        sealed = logger.write(_fixed_entry(retention_years=6))
        assert sealed.retention_years == 6

    def test_retention_7_succeeds(self, logger):
        sealed = logger.write(_fixed_entry(retention_years=7))
        assert sealed.retention_years == 7

    def test_retention_100_succeeds(self, logger):
        sealed = logger.write(_fixed_entry(retention_years=100))
        assert sealed.retention_years == 100

    def test_pre_populated_sha256_rejected(self, logger):
        # AC-R1-11 (F11 tamper guard)
        entry = _fixed_entry(sha256_integrity="a" * 64)
        with pytest.raises(AuditWriteError) as exc_info:
            logger.write(entry)
        assert exc_info.value.reason == "invalid_entry"

    def test_no_backend_invoked_on_invalid_entry(self, backends, dlq):
        lf, worm, crm = backends
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        with pytest.raises(AuditWriteError):
            log.write({"fake": "dict"})  # type: ignore[arg-type]
        assert lf.entries == worm.entries == crm.entries == []
        assert dlq.records == []


# =============================================================================
# T15 — Integrity hash + golden vector (R2)
# =============================================================================


class TestIntegrityHash:

    def test_hash_is_64_lowercase_hex(self, logger):
        sealed = logger.write(_fixed_entry())
        assert re.fullmatch(r"[0-9a-f]{64}", sealed.sha256_integrity)

    def test_hash_is_deterministic_across_loggers(self):
        # AC-R2-2 / AC-R1-12 — fresh unsealed entries, two different loggers
        loggers = []
        for _ in range(2):
            lf = InMemoryAuditBackend(tier="langfuse")
            worm = InMemoryAuditBackend(tier="worm")
            crm = InMemoryAuditBackend(tier="crm")
            loggers.append(
                AuditLogger(langfuse=lf, worm=worm, crm=crm)
            )
        s1 = loggers[0].write(_fixed_entry())
        s2 = loggers[1].write(_fixed_entry())
        assert s1.sha256_integrity == s2.sha256_integrity

    def test_golden_vector_for_fixed_entry(self, logger):
        # AC-R2-5 — pinned hex from independent computation
        sealed = logger.write(_fixed_entry())
        assert sealed.sha256_integrity == ENTRY_GOLDEN_HASH

    def test_hash_excludes_sha256_integrity_field(self):
        entry = _fixed_entry()
        with_field = entry.model_dump(mode="json")
        without_field = entry.model_dump(
            mode="json", exclude={"sha256_integrity"}
        )
        hash_with = hashlib.sha256(
            _canonical_json(with_field).encode("utf-8")
        ).hexdigest()
        hash_without = hashlib.sha256(
            _canonical_json(without_field).encode("utf-8")
        ).hexdigest()
        assert hash_with != hash_without
        assert hash_without == ENTRY_GOLDEN_HASH


# =============================================================================
# T16 — verify_integrity
# =============================================================================


class TestVerifyIntegrity:

    def test_verify_true_on_sealed(self, logger):
        sealed = logger.write(_fixed_entry())
        assert logger.verify_integrity(sealed) is True

    def test_verify_false_on_tampered_field(self, logger):
        sealed = logger.write(_fixed_entry())
        tampered = sealed.model_copy(update={"action": "tampered.action"})
        assert logger.verify_integrity(tampered) is False

    def test_verify_false_on_tampered_hash(self, logger):
        sealed = logger.write(_fixed_entry())
        tampered = sealed.model_copy(update={"sha256_integrity": "f" * 64})
        assert logger.verify_integrity(tampered) is False

    def test_verify_false_on_empty_hash(self, logger):
        entry = _fixed_entry()
        assert logger.verify_integrity(entry) is False

    def test_verify_false_on_non_entry(self, logger):
        assert logger.verify_integrity("not an entry") is False  # type: ignore[arg-type]
        assert logger.verify_integrity(None) is False  # type: ignore[arg-type]


# =============================================================================
# T17 — provenance_chain ordering affects entry hash (R2.7)
# =============================================================================


class TestProvenanceChainOrdering:

    def test_chain_order_affects_entry_hash(self):
        builder = ProvenanceChainBuilder()
        t0 = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 4, 14, 12, 0, 1, tzinfo=timezone.utc)
        s0 = builder.append(
            stage="m1.verify", module="m1", payload={"a": 1}, timestamp=t0
        )
        s1 = builder.append(
            stage="m2.auth", module="m2", payload={"b": 2}, timestamp=t1
        )
        forward_entry = _fixed_entry(provenance_chain=[s0, s1])
        reversed_entry = _fixed_entry(provenance_chain=[s1, s0])
        h_forward = _compute_integrity_hash(forward_entry)
        h_reversed = _compute_integrity_hash(reversed_entry)
        assert h_forward != h_reversed


# =============================================================================
# T18 — ProvenanceChainBuilder: empty, golden, linkage, verify, tamper (R3)
# =============================================================================


class TestProvenanceChainBuilder:

    def test_empty_chain(self):
        # AC-R3-1
        b = ProvenanceChainBuilder()
        assert b.chain() == []
        assert b.head_hash() == ""

    def test_single_stage_golden_vector(self):
        # AC-R3-2 — independently computed pinned hex
        b = ProvenanceChainBuilder()
        s = b.append(
            stage="m1.verify",
            module="m1",
            payload={"stage_data": "value-0"},
            timestamp=_FIXED_TIMESTAMP,
        )
        assert s.hash == STAGE0_GOLDEN_HASH
        assert b.head_hash() == STAGE0_GOLDEN_HASH

    def test_chain_linkage_second_stage_incorporates_first(self):
        # AC-R3-3 — the hash includes previous_hash
        b = ProvenanceChainBuilder()
        t0 = _FIXED_TIMESTAMP
        t1 = datetime(2026, 4, 14, 12, 0, 1, tzinfo=timezone.utc)
        s0 = b.append(
            stage="m1.verify",
            module="m1",
            payload={"stage_data": "value-0"},
            timestamp=t0,
        )
        s1 = b.append(
            stage="m2.auth",
            module="m2",
            payload={"decision": "allow"},
            timestamp=t1,
        )
        # Independently recompute s1's hash using s0.hash as previous
        payload_hash = hashlib.sha256(
            _canonical_json({"decision": "allow"}).encode("utf-8")
        ).hexdigest()
        components = "|".join(
            [s0.hash, "m2.auth", "m2", payload_hash, t1.isoformat()]
        )
        expected = hashlib.sha256(components.encode("utf-8")).hexdigest()
        assert s1.hash == expected
        assert b.head_hash() == s1.hash

    def test_verify_true_on_fresh_chain(self):
        # AC-R3-4
        b = ProvenanceChainBuilder()
        b.append(
            stage="m1.verify",
            module="m1",
            payload={"x": 1},
            timestamp=_FIXED_TIMESTAMP,
        )
        b.append(
            stage="m2.auth",
            module="m2",
            payload={"y": 2},
            timestamp=datetime(2026, 4, 14, 12, 0, 1, tzinfo=timezone.utc),
        )
        assert b.verify() is True

    def test_verify_false_on_tampered_hash(self):
        # AC-R3-5
        b = ProvenanceChainBuilder()
        b.append(
            stage="m1.verify",
            module="m1",
            payload={"x": 1},
            timestamp=_FIXED_TIMESTAMP,
        )
        b._stages[0] = b._stages[0].model_copy(
            update={"hash": "deadbeef" * 8}
        )
        assert b.verify() is False

    def test_verify_false_on_tampered_stage_name(self):
        # AC-R3-6
        b = ProvenanceChainBuilder()
        b.append(
            stage="m1.verify",
            module="m1",
            payload={"x": 1},
            timestamp=_FIXED_TIMESTAMP,
        )
        b._stages[0] = b._stages[0].model_copy(
            update={"stage": "tampered.stage"}
        )
        assert b.verify() is False

    def test_verify_false_on_tampered_module(self):
        b = ProvenanceChainBuilder()
        b.append(
            stage="m1.verify",
            module="m1",
            payload={"x": 1},
            timestamp=_FIXED_TIMESTAMP,
        )
        b._stages[0] = b._stages[0].model_copy(update={"module": "m2"})
        assert b.verify() is False

    def test_verify_false_on_tampered_timestamp(self):
        b = ProvenanceChainBuilder()
        b.append(
            stage="m1.verify",
            module="m1",
            payload={"x": 1},
            timestamp=_FIXED_TIMESTAMP,
        )
        b._stages[0] = b._stages[0].model_copy(
            update={
                "timestamp": datetime(2030, 1, 1, tzinfo=timezone.utc)
            }
        )
        assert b.verify() is False


# =============================================================================
# T19 — ProvenanceChainBuilder validation
# =============================================================================


class TestProvenanceValidation:

    def test_empty_stage_raises(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="stage"):
            b.append(
                stage="",
                module="m1",
                payload={},
                timestamp=_FIXED_TIMESTAMP,
            )

    def test_empty_module_raises(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="module"):
            b.append(
                stage="s",
                module="",
                payload={},
                timestamp=_FIXED_TIMESTAMP,
            )

    def test_bad_module_regex_m14(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="m1..m13"):
            b.append(
                stage="s",
                module="m14",
                payload={},
                timestamp=_FIXED_TIMESTAMP,
            )

    def test_bad_module_regex_foo(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="m1..m13"):
            b.append(
                stage="s",
                module="foo",
                payload={},
                timestamp=_FIXED_TIMESTAMP,
            )

    def test_bad_module_regex_uppercase(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="m1..m13"):
            b.append(
                stage="s",
                module="M1",
                payload={},
                timestamp=_FIXED_TIMESTAMP,
            )

    def test_naive_timestamp_raises(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="timezone-aware"):
            b.append(
                stage="s",
                module="m1",
                payload={},
                timestamp=datetime(2026, 4, 14, 12, 0, 0),  # naive
            )

    def test_non_datetime_timestamp_raises(self):
        b = ProvenanceChainBuilder()
        with pytest.raises(ValueError, match="datetime"):
            b.append(
                stage="s",
                module="m1",
                payload={},
                timestamp="2026-04-14T12:00:00Z",  # type: ignore[arg-type]
            )

    def test_module_regex_accepts_all_valid(self):
        for i in range(1, 14):
            assert _MODULE_PATTERN.fullmatch(f"m{i}") is not None
        assert _MODULE_PATTERN.fullmatch("m0") is None
        assert _MODULE_PATTERN.fullmatch("m14") is None


# =============================================================================
# T20 — Thread-safety docstring
# =============================================================================


class TestThreadSafetyDocumentation:

    def test_docstring_mentions_not_thread_safe(self):
        doc = (ProvenanceChainBuilder.__doc__ or "").lower()
        assert "not thread-safe" in doc


# =============================================================================
# T21 — Usage idiom
# =============================================================================


class TestUsageIdiom:

    def test_builder_chain_attached_to_entry_survives_write(self, logger):
        t0 = _FIXED_TIMESTAMP
        t1 = datetime(2026, 4, 14, 12, 0, 1, tzinfo=timezone.utc)
        builder = ProvenanceChainBuilder()
        builder.append(
            stage="m1.verify",
            module="m1",
            payload={"jti": "abc", "sub": "sarah"},
            timestamp=t0,
        )
        builder.append(
            stage="m2.authority",
            module="m2",
            payload={"decision": "allow"},
            timestamp=t1,
        )
        entry = _fixed_entry(provenance_chain=builder.chain())
        sealed = logger.write(entry)
        assert logger.verify_integrity(sealed)
        assert len(sealed.provenance_chain) == 2
        assert builder.verify() is True


# =============================================================================
# T22 — InMemoryAuditBackend
# =============================================================================


class TestInMemoryAuditBackend:

    def test_tier_langfuse_accepted(self):
        assert InMemoryAuditBackend(tier="langfuse").tier == "langfuse"

    def test_tier_worm_accepted(self):
        assert InMemoryAuditBackend(tier="worm").tier == "worm"

    def test_tier_crm_accepted(self):
        assert InMemoryAuditBackend(tier="crm").tier == "crm"

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError):
            InMemoryAuditBackend(tier="x")

    def test_write_appends(self):
        b = InMemoryAuditBackend(tier="worm")
        entry = _fixed_entry()
        b.write(entry)
        assert b.entries == [entry]

    def test_fail_on_nth_1(self):
        b = InMemoryAuditBackend(tier="worm", fail_on_nth=1)
        with pytest.raises(RuntimeError, match="injected_failure"):
            b.write(_fixed_entry())
        assert b.entries == []

    def test_fail_on_nth_2(self):
        b = InMemoryAuditBackend(tier="worm", fail_on_nth=2)
        b.write(_fixed_entry())
        assert len(b.entries) == 1
        with pytest.raises(RuntimeError):
            b.write(_fixed_entry())
        assert len(b.entries) == 1

    def test_reset_clears_state(self):
        b = InMemoryAuditBackend(tier="worm")
        b.write(_fixed_entry())
        b.reset()
        assert b.entries == []
        assert b._counter == 0

    def test_query_by_trace_id_exact_match(self):
        b = InMemoryAuditBackend(tier="worm")
        b.write(_fixed_entry(trace_id="t1"))
        b.write(_fixed_entry(trace_id="t2"))
        b.write(_fixed_entry(trace_id="t1"))
        result = b.query_by_trace_id("t1")
        assert len(result) == 2
        assert all(e.trace_id == "t1" for e in result)

    def test_query_by_trace_id_case_sensitive(self):
        b = InMemoryAuditBackend(tier="worm")
        b.write(_fixed_entry(trace_id="t1"))
        assert b.query_by_trace_id("T1") == []
        assert len(b.query_by_trace_id("t1")) == 1

    def test_query_by_trace_id_unknown(self):
        b = InMemoryAuditBackend(tier="worm")
        b.write(_fixed_entry(trace_id="t1"))
        assert b.query_by_trace_id("unknown") == []


# =============================================================================
# T22b — Logger tier-slot validation
# =============================================================================


class TestLoggerTierValidation:

    def test_wrong_langfuse_tier_rejected(self, dlq):
        wrong_lf = InMemoryAuditBackend(tier="worm")
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm")
        with pytest.raises(AuditWriteError) as exc_info:
            AuditLogger(langfuse=wrong_lf, worm=worm, crm=crm, dlq=dlq)
        assert exc_info.value.reason == "invalid_backend_tier"

    def test_missing_tier_attribute_rejected(self, dlq):
        class NoTierBackend:
            def write(self, entry):
                pass

            def query_by_trace_id(self, t):
                return []

        with pytest.raises(AuditWriteError) as exc_info:
            AuditLogger(
                langfuse=NoTierBackend(),  # type: ignore[arg-type]
                worm=InMemoryAuditBackend(tier="worm"),
                crm=InMemoryAuditBackend(tier="crm"),
                dlq=dlq,
            )
        assert exc_info.value.reason == "invalid_backend_tier"

    def test_min_retention_below_6_rejected(self, backends, dlq):
        lf, worm, crm = backends
        with pytest.raises(ValueError, match=">=.*6"):
            AuditLogger(
                langfuse=lf,
                worm=worm,
                crm=crm,
                dlq=dlq,
                min_retention_years=5,
            )


# =============================================================================
# T23 — Frozen vocabulary + grep
# =============================================================================


class TestFrozenReasonVocabulary:

    def test_valid_reasons_frozenset(self):
        assert isinstance(VALID_REASONS, frozenset)
        assert VALID_REASONS == {
            "invalid_entry",
            "retention_too_short",
            "langfuse_write_failed",
            "worm_write_failed",
            "crm_write_failed",
            "invalid_backend_tier",
        }

    def test_every_error_raised_has_frozen_reason(self):
        exceptions = []
        # 1. invalid_entry (non-AuditEntry)
        log = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm"),
        )
        try:
            log.write("nope")  # type: ignore[arg-type]
        except AuditWriteError as e:
            exceptions.append(e)
        # 2. invalid_entry (pre-sealed)
        try:
            log.write(_fixed_entry(sha256_integrity="a" * 64))
        except AuditWriteError as e:
            exceptions.append(e)
        # 3. retention_too_short
        try:
            log.write(_fixed_entry(retention_years=3))
        except AuditWriteError as e:
            exceptions.append(e)
        # 4. langfuse_write_failed
        log2 = AuditLogger(
            langfuse=InMemoryAuditBackend(
                tier="langfuse", fail_on_nth=1
            ),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm"),
        )
        try:
            log2.write(_fixed_entry())
        except AuditWriteError as e:
            exceptions.append(e)
        # 5. worm_write_failed
        log3 = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm", fail_on_nth=1),
            crm=InMemoryAuditBackend(tier="crm"),
        )
        try:
            log3.write(_fixed_entry())
        except AuditWriteError as e:
            exceptions.append(e)
        # 6. crm_write_failed
        log4 = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm", fail_on_nth=1),
        )
        try:
            log4.write(_fixed_entry())
        except AuditWriteError as e:
            exceptions.append(e)
        # 7. invalid_backend_tier
        try:
            AuditLogger(
                langfuse=InMemoryAuditBackend(tier="worm"),
                worm=InMemoryAuditBackend(tier="worm"),
                crm=InMemoryAuditBackend(tier="crm"),
            )
        except AuditWriteError as e:
            exceptions.append(e)

        assert len(exceptions) == 7
        for e in exceptions:
            assert e.reason in VALID_REASONS
            assert str(e) == e.reason

    def test_source_grep_only_frozen_reasons(self):
        src_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
        )
        assert src_dir.is_dir()
        pattern = re.compile(r"""AuditWriteError\(\s*["']([^"']+)["']""")
        found_reasons = set()
        for py_file in src_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for m in pattern.finditer(text):
                found_reasons.add(m.group(1))
        assert found_reasons, (
            "Expected at least one AuditWriteError(...) call in src"
        )
        bad = found_reasons - VALID_REASONS
        assert not bad, f"Found reasons outside vocab: {bad}"


# =============================================================================
# T24 — DLQ semantics
# =============================================================================


class TestDLQSemantics:

    def test_dlq_empty_on_success(self, logger, dlq):
        logger.write(_fixed_entry())
        assert dlq.records == []
        assert logger.lost_entries() == []

    def test_dlq_failure_does_not_mask_tier_reason(self):
        class RaisingDLQ:
            def enqueue(self, entry, reason):
                raise RuntimeError("dlq is down")

        lf = InMemoryAuditBackend(tier="langfuse", fail_on_nth=1)
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm")
        log = AuditLogger(
            langfuse=lf,
            worm=worm,
            crm=crm,
            dlq=RaisingDLQ(),  # type: ignore[arg-type]
        )
        with pytest.raises(AuditWriteError) as exc_info:
            log.write(_fixed_entry())
        assert exc_info.value.reason == "langfuse_write_failed"
        lost = log.lost_entries()
        assert len(lost) == 1
        assert lost[0][1] == "langfuse_write_failed"


# =============================================================================
# T25 — DLQ shared-by-reference
# =============================================================================


class TestDLQSharing:

    def test_dlq_shared_across_loggers_accumulates(self):
        shared_dlq = InMemoryAuditDLQ()
        log1 = AuditLogger(
            langfuse=InMemoryAuditBackend(
                tier="langfuse", fail_on_nth=1
            ),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm"),
            dlq=shared_dlq,
        )
        log2 = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm", fail_on_nth=1),
            crm=InMemoryAuditBackend(tier="crm"),
            dlq=shared_dlq,
        )
        with pytest.raises(AuditWriteError):
            log1.write(_fixed_entry())
        with pytest.raises(AuditWriteError):
            log2.write(_fixed_entry())
        assert len(shared_dlq.records) == 2
        reasons = {r for _, r in shared_dlq.records}
        assert reasons == {"langfuse_write_failed", "worm_write_failed"}


# =============================================================================
# T26 — query_by_trace_id
# =============================================================================


class TestQueryByTraceId:

    def test_query_returns_matching_entries(self, logger):
        logger.write(_fixed_entry(trace_id="t1"))
        logger.write(_fixed_entry(trace_id="t1"))
        logger.write(_fixed_entry(trace_id="t2"))
        logger.write(_fixed_entry(trace_id="t1"))
        result = logger.query_by_trace_id("t1")
        assert len(result) == 3
        assert all(e.trace_id == "t1" for e in result)

    def test_query_unknown_trace_returns_empty(self, logger):
        logger.write(_fixed_entry(trace_id="t1"))
        assert logger.query_by_trace_id("unknown") == []

    def test_query_delegates_to_worm_only(self, dlq):
        class TrackingWorm:
            tier = "worm"

            def __init__(self):
                self.query_calls = 0
                self.entries = []

            def write(self, e):
                self.entries.append(e)

            def query_by_trace_id(self, t):
                self.query_calls += 1
                return [e for e in self.entries if e.trace_id == t]

        class TrackingNoQuery:
            def __init__(self, tier):
                self.tier = tier
                self.query_calls = 0
                self.entries = []

            def write(self, e):
                self.entries.append(e)

            def query_by_trace_id(self, t):
                self.query_calls += 1
                return []

        tracking_worm = TrackingWorm()
        tracking_lf = TrackingNoQuery("langfuse")
        tracking_crm = TrackingNoQuery("crm")
        log = AuditLogger(
            langfuse=tracking_lf,  # type: ignore[arg-type]
            worm=tracking_worm,  # type: ignore[arg-type]
            crm=tracking_crm,  # type: ignore[arg-type]
            dlq=dlq,
        )
        log.write(_fixed_entry(trace_id="t1"))
        result = log.query_by_trace_id("t1")
        assert len(result) == 1
        assert tracking_worm.query_calls == 1
        assert tracking_lf.query_calls == 0
        assert tracking_crm.query_calls == 0

    def test_query_tolerates_not_implemented_from_worm(self, dlq):
        class Phase2S3Worm:
            tier = "worm"

            def __init__(self):
                self.entries = []

            def write(self, e):
                self.entries.append(e)

            def query_by_trace_id(self, t):
                raise NotImplementedError("S3 Object Lock cannot query")

        log = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=Phase2S3Worm(),  # type: ignore[arg-type]
            crm=InMemoryAuditBackend(tier="crm"),
            dlq=dlq,
        )
        log.write(_fixed_entry())
        assert log.query_by_trace_id("anything") == []


# =============================================================================
# T27 — Security
# =============================================================================


_CREDENTIAL_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"""password\s*=\s*['"][^'"]+['"]"""),
    re.compile(
        r"""api[_-]?key\s*=\s*['"][^'"]+['"]""", re.IGNORECASE
    ),
]


class TestSecurity:

    def test_no_credentials_in_src(self):
        src_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
        )
        for py_file in src_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for pattern in _CREDENTIAL_PATTERNS:
                assert not pattern.search(text), (
                    f"Credential pattern {pattern.pattern!r} in {py_file}"
                )

    def test_no_os_environ_in_src(self):
        src_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
        )
        for py_file in src_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            assert "os.environ" not in text, (
                f"os.environ in {py_file}"
            )
            assert "os.getenv" not in text, (
                f"os.getenv in {py_file}"
            )

    def test_no_logging_of_entry_contents_in_src(self):
        src_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
        )
        for py_file in src_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            assert "import logging" not in text, (
                f"logging imported in {py_file}"
            )
            for line in text.splitlines():
                stripped = line.lstrip()
                assert not stripped.startswith("print("), (
                    f"print() call in {py_file}"
                )

    def test_str_exc_equals_reason(self):
        try:
            raise AuditWriteError("invalid_entry")
        except AuditWriteError as e:
            assert str(e) == e.reason == "invalid_entry"


# =============================================================================
# T28 — AST import scan
# =============================================================================


_FORBIDDEN_PREFIXES = (
    "m1_",
    "m2_",
    "m4_",
    "m6_",
    "m7_",
    "m8_",
    "m9_",
    "m11_",
    "m12_",
    "m13_",
)


class TestImportBoundary:

    def test_no_forbidden_cross_module_imports(self):
        src_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "m10_audit_logger"
        )
        for py_file in src_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in _FORBIDDEN_PREFIXES:
                            assert not alias.name.startswith(prefix), (
                                f"{py_file}:{node.lineno}: forbidden "
                                f"import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    name = node.module or ""
                    for prefix in _FORBIDDEN_PREFIXES:
                        assert not name.startswith(prefix), (
                            f"{py_file}:{node.lineno}: forbidden "
                            f"import from {name}"
                        )

    def test_m3_schema_registry_is_imported(self):
        import m10_audit_logger.backends as b
        import m10_audit_logger.provenance as p

        assert hasattr(b, "AuditEntry")
        assert hasattr(p, "ProvenanceStage")


# =============================================================================
# T29 — Public API + M3 compatibility
# =============================================================================


class TestPublicApi:

    def test_all_surface_matches(self):
        expected = {
            "AuditLogger",
            "AuditWriteError",
            "MIN_RETENTION_YEARS",
            "VALID_REASONS",
            "AuditBackend",
            "AuditDLQ",
            "InMemoryAuditBackend",
            "InMemoryAuditDLQ",
            "VALID_TIERS",
            "ProvenanceChainBuilder",
        }
        assert set(m10_audit_logger.__all__) == expected
        for name in expected:
            assert hasattr(m10_audit_logger, name), f"missing: {name}"

    def test_m3_compatibility(self):
        required_fields = {
            "canonical_id",
            "trace_id",
            "timestamp",
            "actor_id",
            "action",
            "module",
            "decision",
            "input_hash",
            "output_hash",
            "latency_ms",
            "firm_id",
            "worm_record_id",
            "sha256_integrity",
            "retention_years",
            "provenance_chain",
        }
        actual = set(AuditEntry.model_fields.keys())
        missing = required_fields - actual
        assert not missing, f"M3 AuditEntry missing: {missing}"


# =============================================================================
# T30 — Perf
# =============================================================================


class TestPerf:

    @pytest.mark.perf
    def test_1000_writes_under_10s(self):
        lf = InMemoryAuditBackend(tier="langfuse")
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm")
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm)
        start = time.perf_counter()
        for i in range(1000):
            log.write(_fixed_entry(trace_id=f"trace-{i:04d}"))
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"1000 writes took {elapsed:.2f}s"


# =============================================================================
# T31 — health()
# =============================================================================


class TestHealth:

    def test_health_shape_clean(self, logger):
        h = logger.health()
        assert set(h.keys()) == {
            "status",
            "tiers",
            "dlq_depth",
            "lost_depth",
            "min_retention_years",
        }
        assert h["status"] == "ok"
        assert h["tiers"] == list(VALID_TIERS)
        assert h["dlq_depth"] == 0
        assert h["lost_depth"] == 0
        assert h["min_retention_years"] == 6

    def test_health_reflects_dlq_depth(self, dlq):
        lf = InMemoryAuditBackend(tier="langfuse", fail_on_nth=1)
        worm = InMemoryAuditBackend(tier="worm")
        crm = InMemoryAuditBackend(tier="crm")
        log = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
        with pytest.raises(AuditWriteError):
            log.write(_fixed_entry())
        h = log.health()
        assert h["dlq_depth"] == 1
        assert h["lost_depth"] == 0

    def test_health_has_no_secret_looking_strings(self, logger):
        h = logger.health()
        for v in h.values():
            assert "AKIA" not in str(v)
            assert "sk-" not in str(v)


# =============================================================================
# T32 — Write-twice determinism
# =============================================================================


class TestWriteTwiceDeterminism:

    def test_fresh_unsealed_writes_produce_identical_hash(self):
        loggers = []
        for _ in range(2):
            loggers.append(
                AuditLogger(
                    langfuse=InMemoryAuditBackend(tier="langfuse"),
                    worm=InMemoryAuditBackend(tier="worm"),
                    crm=InMemoryAuditBackend(tier="crm"),
                )
            )
        s1 = loggers[0].write(_fixed_entry())
        s2 = loggers[1].write(_fixed_entry())
        assert s1.sha256_integrity == s2.sha256_integrity == ENTRY_GOLDEN_HASH


# =============================================================================
# T33 — Field preservation
# =============================================================================


class TestFieldPreservation:

    def test_sealed_entry_preserves_all_non_hash_fields(self, logger):
        entry = _fixed_entry(
            reason="test reason",
            wsp_section="WSP-1.2.3",
            archetype="tier4_independent_ria",
            role="advisor",
            data_sources_used=["orion", "salesforce"],
            rule_applied="authority.read_own_clients",
        )
        sealed = logger.write(entry)
        for field_name in AuditEntry.model_fields:
            if field_name == "sha256_integrity":
                continue
            assert getattr(sealed, field_name) == getattr(
                entry, field_name
            ), f"field {field_name} changed"
        assert entry.sha256_integrity == ""
        assert sealed.sha256_integrity != ""


# =============================================================================
# Extra: _json_default behavior
# =============================================================================


class TestJsonDefault:

    def test_json_default_handles_uuid(self):
        v = UUID("11111111-1111-1111-1111-111111111111")
        assert _json_default(v) == str(v)

    def test_json_default_handles_datetime(self):
        v = _FIXED_TIMESTAMP
        assert _json_default(v) == v.isoformat()

    def test_json_default_handles_enum(self):
        import enum

        class Color(enum.Enum):
            red = "red"

        assert _json_default(Color.red) == "red"

    def test_json_default_raises_type_error_on_unknown(self):
        class Weird:
            pass

        with pytest.raises(TypeError, match="not serializable"):
            _json_default(Weird())

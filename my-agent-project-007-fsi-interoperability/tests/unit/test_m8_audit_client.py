"""Task 1 v0.2.0 NEW -- AuditClient Protocol + FakeAuditClient + AuditEmitError."""

import pytest

from m8_pipeline_engine.audit_client import (
    AuditClient,
    AuditEmitError,
    FakeAuditClient,
)


def test_fake_audit_satisfies_protocol():
    assert isinstance(FakeAuditClient(), AuditClient)


def test_fake_audit_records_entries():
    c = FakeAuditClient()
    c.emit({"source": "m8", "event_type": "m8.test", "n": 1})
    c.emit({"source": "m8", "event_type": "m8.test", "n": 2})
    assert len(c.entries) == 2
    assert c.entries[0]["n"] == 1


def test_fake_audit_fail_at_triggers_raise():
    c = FakeAuditClient(fail_at=2)
    c.emit({"source": "m8", "n": 1})
    with pytest.raises(AuditEmitError):
        c.emit({"source": "m8", "n": 2})


def test_audit_emit_error_inherits_exception():
    assert issubclass(AuditEmitError, Exception)

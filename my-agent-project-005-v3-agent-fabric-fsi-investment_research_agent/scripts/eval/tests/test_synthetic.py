"""
Unit tests (mocked) for the 4 synthetic gateway-policy tests.

Each synthetic test function exposes a `dry_run=True` path that does not
talk to AWS/SF. We test BOTH the dry-run path (fast, CI-safe) AND the live
path by monkey-patching http_post / query_audit_log / subprocess.run so we
can inspect behavior without actually hitting Lambda or Salesforce.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS_EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_EVAL))

import synthetic_tests as st  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Dry-run coverage (each test passes in dry-run)
# ─────────────────────────────────────────────────────────────


def test_mnpi_redaction_dry_run_passes():
    r = st.test_mnpi_redaction(
        url="", token="", username="", dry_run=True,
    )
    assert r.name == "mnpi_redaction"
    assert r.passed is True
    assert r.details["audit_redactions_observed"] > 0
    assert r.details["leaked_fields"] == []


def test_rate_limit_dry_run_passes():
    r = st.test_rate_limit(url="", token="", dry_run=True)
    assert r.name == "rate_limit"
    assert r.passed is True
    assert r.details["status_2xx"] == st.RATE_LIMIT_EXPECTED_SUCCESS
    assert r.details["status_429"] == st.RATE_LIMIT_EXPECTED_THROTTLE


def test_circuit_breaker_dry_run_passes():
    r = st.test_circuit_breaker(
        url="", token="", lambda_name="fake-lambda",
        env_var="FAKE_ENV", dry_run=True,
    )
    assert r.name == "circuit_breaker"
    assert r.passed is True
    assert r.details["post_break_status"] == 503
    assert r.details["recovery_status"] < 400
    assert "restore" in r.details["cleanup_step"].lower()


def test_finra_audit_dry_run_passes():
    r = st.test_finra_audit(
        url="", token="", username="", dry_run=True,
    )
    assert r.name == "finra_audit"
    assert r.passed is True
    assert r.details["audit_has_gateway_stage"] is True


# ─────────────────────────────────────────────────────────────
# Live-path unit tests — mock HTTP and SF CLI / AWS CLI
# ─────────────────────────────────────────────────────────────


def _fake_post(status=200, payload=None, headers=None):
    def _fn(url, body, hdrs, timeout=30):
        return status, payload or {}, headers or {}
    return _fn


def test_mnpi_redaction_live_detects_leak(monkeypatch):
    """If the response text contains FinServ__MarketValue__c verbatim, test FAILS."""
    leaky_payload = {
        "response": "Holdings: FinServ__MarketValue__c = $1,234,567",
    }
    monkeypatch.setattr(st, "http_post", _fake_post(200, leaky_payload, {}))
    monkeypatch.setattr(st, "query_audit_log", lambda *a, **k: [
        {"Pipeline_Stage__c": "gateway", "Event_Type__c": "MNPI_REDACTION"},
    ])
    r = st.test_mnpi_redaction(
        url="https://example/agent/query", token="t", username="alias",
        dry_run=False,
    )
    assert r.passed is False
    assert "FinServ__MarketValue__c" in r.details["leaked_fields"]


def test_mnpi_redaction_live_happy_path(monkeypatch):
    clean = {"response": "Holdings: [REDACTED], shares: [REDACTED]"}
    monkeypatch.setattr(st, "http_post",
                        _fake_post(200, clean, {"x-mnpi-redactions": "2"}))
    monkeypatch.setattr(st, "query_audit_log", lambda *a, **k: [
        {"Pipeline_Stage__c": "gateway", "Event_Type__c": "MNPI_REDACTION"},
        {"Pipeline_Stage__c": "gateway", "Event_Type__c": "mnpi_redact"},
    ])
    r = st.test_mnpi_redaction(
        url="https://example/agent/query", token="t", username="alias",
        dry_run=False,
    )
    assert r.passed is True
    assert r.details["leaked_fields"] == []
    assert r.details["audit_redactions_observed"] == 2


def test_rate_limit_live_counts_429s(monkeypatch):
    counter = {"n": 0}
    lock_needed = False  # threading-safe increment isn't strict here

    def _post(url, body, hdrs, timeout=30):
        counter["n"] += 1
        status = 200 if counter["n"] <= st.RATE_LIMIT_EXPECTED_SUCCESS else 429
        return status, {}, {}

    monkeypatch.setattr(st, "http_post", _post)
    r = st.test_rate_limit(
        url="https://example/agent/query", token="t", dry_run=False,
    )
    assert r.passed is True
    assert r.details["status_2xx"] >= st.RATE_LIMIT_EXPECTED_SUCCESS - 5
    assert r.details["status_429"] >= st.RATE_LIMIT_EXPECTED_THROTTLE - 5


def test_rate_limit_live_fails_if_no_throttle(monkeypatch):
    monkeypatch.setattr(st, "http_post", _fake_post(200, {}, {}))
    r = st.test_rate_limit(
        url="https://example/agent/query", token="t", dry_run=False,
    )
    assert r.passed is False


def test_circuit_breaker_live_happy_path(monkeypatch):
    get_cfg = {"Environment": {"Variables": {"FAKE_ENV": "REAL_VALUE"}}}

    def fake_run(cmd, capture_output, text, timeout):
        if "get-function-configuration" in cmd:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(get_cfg), stderr="",
            )
        if "update-function-configuration" in cmd:
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(st.subprocess, "run", fake_run)

    seq = [
        (502, {}, {}),
        (502, {}, {}),
        (502, {}, {}),
        (503, {}, {"x-circuit-breaker": "open"}),
        (200, {}, {}),
    ]
    idx = {"i": 0}

    def fake_post(url, body, hdrs, timeout=30):
        out = seq[idx["i"]]
        idx["i"] = min(idx["i"] + 1, len(seq) - 1)
        return out

    monkeypatch.setattr(st, "http_post", fake_post)
    monkeypatch.setattr(st.time, "sleep", lambda s: None)

    r = st.test_circuit_breaker(
        url="https://example/agent/query", token="t",
        lambda_name="fake-lambda", env_var="FAKE_ENV",
        dry_run=False, recovery_s=1,
    )
    assert r.passed is True
    assert r.details["post_break_status"] == 503
    assert r.details["cb_tripped_header_seen"] is True
    assert r.details["recovery_status"] == 200
    assert "restored" in r.details["cleanup_step"]


def test_circuit_breaker_live_always_restores(monkeypatch):
    """Even when the break call throws, the env var must be restored."""
    get_cfg = {"Environment": {"Variables": {"FAKE_ENV": "REAL_VALUE"}}}
    restores: list[dict] = []

    def fake_run(cmd, capture_output, text, timeout):
        if "get-function-configuration" in cmd:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(get_cfg), stderr="",
            )
        if "update-function-configuration" in cmd:
            env_idx = cmd.index("--environment") + 1
            payload = json.loads(cmd[env_idx])
            restores.append(payload["Variables"])
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(st.subprocess, "run", fake_run)

    def boom(*a, **k):
        raise RuntimeError("network down mid-test")

    monkeypatch.setattr(st, "http_post", boom)
    monkeypatch.setattr(st.time, "sleep", lambda s: None)

    r = st.test_circuit_breaker(
        url="https://example/agent/query", token="t",
        lambda_name="fake-lambda", env_var="FAKE_ENV",
        dry_run=False, recovery_s=1,
    )
    # First update = break (BOGUS); last update = restore (REAL_VALUE)
    assert any(v.get("FAKE_ENV") == "BOGUS_VALUE_FOR_CB_TEST" for v in restores)
    assert restores[-1].get("FAKE_ENV") == "REAL_VALUE"
    # The test itself should not pass due to the raised exception
    assert r.passed is False


def test_circuit_breaker_live_missing_config():
    r = st.test_circuit_breaker(
        url="https://example", token="t",
        lambda_name="", env_var="", dry_run=False,
    )
    assert r.passed is False
    assert r.error == "missing config"


def test_finra_audit_live_happy_path(monkeypatch):
    monkeypatch.setattr(st, "http_post", _fake_post(200, {"response": "ok"}, {}))
    monkeypatch.setattr(st, "query_audit_log",
                        lambda *a, **k: [{"Pipeline_Stage__c": "gateway"}])
    monkeypatch.setattr(st.time, "sleep", lambda s: None)
    r = st.test_finra_audit(
        url="https://example/agent/query", token="t",
        username="alias", dry_run=False,
    )
    assert r.passed is True
    assert r.details["audit_has_gateway_stage"] is True


def test_finra_audit_live_fails_when_no_audit(monkeypatch):
    monkeypatch.setattr(st, "http_post", _fake_post(200, {"response": "ok"}, {}))
    monkeypatch.setattr(st, "query_audit_log", lambda *a, **k: [])
    monkeypatch.setattr(st.time, "sleep", lambda s: None)
    r = st.test_finra_audit(
        url="https://example/agent/query", token="t",
        username="alias", dry_run=False,
    )
    assert r.passed is False
    assert r.details["audit_records_found"] == 0


# ─────────────────────────────────────────────────────────────
# Integration: main() in dry-run
# ─────────────────────────────────────────────────────────────


def test_main_dry_run_all_tests(tmp_path):
    rc = st.main(["--dry-run", "--out-dir", str(tmp_path)])
    assert rc == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["pass_count"] == 4
    assert latest["fail_count"] == 0
    names = {r["name"] for r in latest["results"]}
    assert names == {"mnpi_redaction", "rate_limit",
                     "circuit_breaker", "finra_audit"}


def test_main_only_filter(tmp_path):
    rc = st.main(["--dry-run", "--out-dir", str(tmp_path),
                  "--only", "mnpi_redaction,finra_audit"])
    assert rc == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["total"] == 2

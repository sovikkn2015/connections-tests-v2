"""Trust layer — gate_enforcer, mnpi_filter, idp_session."""

from __future__ import annotations

import time

import pytest

from openclaw.trust import (
    GateEnforcer,
    GateViolation,
    MNPIFilter,
    MNPIViolation,
    SessionTokenMinter,
    SessionTokenInvalid,
)
from openclaw.orchestration.topology import AGENT_TOPOLOGY


# --------------------------- gate_enforcer --------------------------------


def test_gate_allows_configured_tool() -> None:
    ge = GateEnforcer()
    # market_specialist has mcp_invoke in its allowlist.
    ge.check_tool("market_specialist", "mcp_invoke")  # should not raise


def test_gate_denies_tool_outside_allowlist() -> None:
    ge = GateEnforcer()
    with pytest.raises(GateViolation):
        ge.check_tool("market_specialist", "mulesoft_api")


def test_gate_allows_configured_mcp() -> None:
    ge = GateEnforcer()
    ge.check_mcp("market_specialist", "market-data")


def test_gate_denies_mcp_outside_allowlist() -> None:
    ge = GateEnforcer()
    with pytest.raises(GateViolation) as exc:
        ge.check_mcp("faq_specialist", "mulesoft-actions")
    assert exc.value.kind == "mcp"


def test_gate_unknown_agent_raises_registry_error() -> None:
    ge = GateEnforcer()
    with pytest.raises(GateViolation) as exc:
        ge.check_tool("nonexistent_agent", "anything")
    assert exc.value.kind == "registry"


def test_gate_read_only_agent_blocks_writes() -> None:
    ge = GateEnforcer()
    with pytest.raises(GateViolation) as exc:
        ge.check_write_safe("faq_specialist")
    assert "READ_ONLY" in exc.value.reason


def test_gate_batch_check_stops_on_first_violation() -> None:
    ge = GateEnforcer()
    with pytest.raises(GateViolation):
        ge.batch_check(
            "market_specialist",
            tools=["rag_retrieve", "not_allowed"],
            mcps=["market-data"],
        )


def test_action_specialist_can_call_all_seven_gates() -> None:
    ge = GateEnforcer()
    for tool in (
        "compliance_screening",
        "hitl",
        "dual_auth",
        "mulesoft_api",
        "audit_logging",
    ):
        ge.check_tool("action_specialist", tool)
    ge.check_mcp("action_specialist", "mulesoft-actions")
    ge.check_mcp("action_specialist", "salesforce-crm")


# --------------------------- mnpi_filter ----------------------------------


def test_mnpi_redacts_dollar_amounts() -> None:
    mf = MNPIFilter(strict=False)
    scrubbed, report = mf.scrub_text(
        "Sell $24,322.50 of NVDA and wire $1.2M to HSBC Singapore."
    )
    assert "$24,322.50" not in scrubbed
    assert "$1.2M" not in scrubbed
    assert report.redactions.get("dollar", 0) >= 2


def test_mnpi_redacts_shares() -> None:
    mf = MNPIFilter(strict=False)
    scrubbed, report = mf.scrub_text("Sell 4,000 shares of NVDA at market.")
    assert "4,000 shares" not in scrubbed
    assert "[SHARES_REDACTED]" in scrubbed
    assert report.redactions.get("shares", 0) >= 1


def test_mnpi_redacts_wire_instructions() -> None:
    mf = MNPIFilter(strict=False)
    scrubbed, report = mf.scrub_text(
        "Please wire $250,000 to HSBC Singapore account 123."
    )
    assert "[WIRE_REDACTED]" in scrubbed
    assert report.redactions.get("wire", 0) >= 1


def test_mnpi_strict_raises_on_insider_phrasing() -> None:
    mf = MNPIFilter(strict=True)
    with pytest.raises(MNPIViolation):
        mf.scrub_text("The company is about to report earnings tomorrow.")


def test_mnpi_lax_mode_redacts_insider_phrasing() -> None:
    mf = MNPIFilter(strict=False)
    scrubbed, report = mf.scrub_text("The company is about to report earnings.")
    assert "[INSIDER_REDACTED]" in scrubbed


def test_mnpi_hard_denies_sentinel() -> None:
    mf = MNPIFilter(strict=False)
    with pytest.raises(MNPIViolation) as exc:
        mf.scrub_text("[MNPI_RAW] holdings 5M of NVDA")
    assert "[MNPI_RAW]" in exc.value.reason


def test_mnpi_scrubs_nested_dict() -> None:
    mf = MNPIFilter(strict=False)
    payload = {
        "client": "Patel",
        "positions": [
            {"ticker": "NVDA", "market_value": "$1,234,567"},
            {"ticker": "AAPL", "shares": "500 shares"},
        ],
        "wire_memo": "wire $50,000 to Chase",
    }
    scrubbed, report = mf.scrub_object(payload)
    # Client name preserved (not MNPI — that's PII with a different filter).
    assert scrubbed["client"] == "Patel"
    assert scrubbed["positions"][0]["market_value"] == "[$REDACTED]"
    assert "SHARES_REDACTED" in scrubbed["positions"][1]["shares"]
    assert "WIRE_REDACTED" in scrubbed["wire_memo"]
    assert report.any_redaction


def test_mnpi_report_counts_are_accurate() -> None:
    mf = MNPIFilter(strict=False)
    _, report = mf.scrub_text("$100, $200, 500 shares")
    assert report.redactions["dollar"] == 2
    assert report.redactions["shares"] == 1


# --------------------------- idp_session ----------------------------------


def test_mint_and_verify_roundtrip() -> None:
    stm = SessionTokenMinter()
    tok = stm.mint(principal_id="u42", persona="fsi_research", channel="slack")
    claims = stm.verify(tok)
    assert claims.principal_id == "u42"
    assert claims.persona == "fsi_research"
    assert claims.channel == "slack"


def test_mint_rejects_unknown_persona() -> None:
    stm = SessionTokenMinter()
    with pytest.raises(ValueError, match="unknown persona"):
        stm.mint(principal_id="u1", persona="fsi_trader")


def test_verify_rejects_tampered_signature() -> None:
    stm = SessionTokenMinter()
    tok = stm.mint(principal_id="u1", persona="fsi_research")
    body, sig = tok.split(".", 1)
    # Flip a character in the signature.
    bad_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(SessionTokenInvalid, match="signature"):
        stm.verify(f"{body}.{bad_sig}")


def test_verify_rejects_expired_token() -> None:
    stm = SessionTokenMinter(default_ttl_s=1)
    tok = stm.mint(principal_id="u1", persona="fsi_research")
    time.sleep(1.2)
    with pytest.raises(SessionTokenInvalid, match="expired"):
        stm.verify(tok)


def test_verify_rejects_malformed_token() -> None:
    stm = SessionTokenMinter()
    with pytest.raises(SessionTokenInvalid, match="malformed"):
        stm.verify("not-a-token")


def test_minter_requires_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTCORE_SESSION_SIGNING_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SIGNING_KEY"):
        SessionTokenMinter()


def test_two_keys_produce_different_tokens() -> None:
    stm_a = SessionTokenMinter(signing_key="aaaa" * 16)
    stm_b = SessionTokenMinter(signing_key="bbbb" * 16)
    tok_a = stm_a.mint(principal_id="u1", persona="fsi_research")
    # B's verifier rejects A's token.
    with pytest.raises(SessionTokenInvalid):
        stm_b.verify(tok_a)

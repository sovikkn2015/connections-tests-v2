"""
M9 Task 6 -- MNPI-shape pre-scan.

AC8.1-8.9: categories, precedence, ABA validator.
"""

from __future__ import annotations

from m9_intent_router.mnpi_scan import _aba_valid, scan_mnpi_shape


# -----------------------------------------------------------------------------
# ABA validator.
# -----------------------------------------------------------------------------


def test_aba_valid_chase_routing():
    """JPMorgan Chase NY routing 021000021 -- valid ABA checksum."""
    assert _aba_valid("021000021") is True


def test_aba_valid_frb_boston():
    """Federal Reserve Bank Boston 011000015 -- valid ABA checksum."""
    assert _aba_valid("011000015") is True


def test_aba_invalid():
    assert _aba_valid("123456789") is False


def test_aba_rejects_non_digit():
    assert _aba_valid("12345678a") is False


def test_aba_rejects_wrong_length():
    assert _aba_valid("12345678") is False


# -----------------------------------------------------------------------------
# Scan categories.
# -----------------------------------------------------------------------------


def test_ssn_dashed_detected():
    assert scan_mnpi_shape("my ssn is 123-45-6789") == "ssn"


def test_routing_number_detected_with_valid_checksum():
    assert scan_mnpi_shape("routing 021000021") == "routing_number"


def test_wire_instruction_compound_signal():
    """Precedence 1: wire keyword + numeric context."""
    assert (
        scan_mnpi_shape("wire $50k to routing 021000021 account 1234567890")
        == "wire_instruction"
    )


def test_bank_account_10_to_17_digits():
    assert scan_mnpi_shape("account 1234567890") == "bank_account"


def test_ssn_bare_9_digit_detected():
    assert scan_mnpi_shape("social 123456789") == "ssn"


def test_no_hit_on_plain_text():
    assert scan_mnpi_shape("hello world") is None


def test_no_hit_on_ticker():
    assert scan_mnpi_shape("watch NVDA today") is None


def test_empty_input():
    assert scan_mnpi_shape("") is None


# -----------------------------------------------------------------------------
# Precedence ordering.
# -----------------------------------------------------------------------------


def test_precedence_wire_over_routing():
    """wire + any routing beats bare routing_number alone."""
    assert scan_mnpi_shape("please wire 021000021 today") == "wire_instruction"


def test_precedence_ssn_dashed_over_bank():
    """ssn dashed takes precedence over bank (no ABA hit here)."""
    assert scan_mnpi_shape("ssn 123-45-6789 and 999999999") == "ssn"


def test_precedence_routing_over_ssn():
    """ABA-valid 9-digit -> routing_number, not ssn."""
    assert scan_mnpi_shape("021000021") == "routing_number"

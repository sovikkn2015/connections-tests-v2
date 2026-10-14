"""
M9 Task 5 -- Entity extraction regex library.

AC6.1-6.8: pure, never raises, keys-only audit, SF checksum, ticker whitelist,
household/account regex, date range.
"""

from __future__ import annotations

from m9_intent_router.regex_library import _validate_sf_id, extract_entities


# -----------------------------------------------------------------------------
# AC6.1 -- pure, missing slots absent.
# -----------------------------------------------------------------------------


def test_empty_utterance_returns_empty_dict():
    assert extract_entities("") == {}


def test_no_entities_returns_empty_dict():
    assert extract_entities("hello world") == {}


def test_missing_slots_are_absent_not_none():
    result = extract_entities("NVDA is up")
    assert "client_id" not in result


# -----------------------------------------------------------------------------
# AC6.2 -- ticker whitelist.
# -----------------------------------------------------------------------------


def test_ticker_positive_whitelist():
    assert extract_entities("watch NVDA today").get("ticker") == "NVDA"
    assert extract_entities("AAPL earnings").get("ticker") == "AAPL"


def test_ticker_rejects_lowercase():
    assert "ticker" not in extract_entities("watch nvda today")


def test_ticker_rejects_six_chars():
    assert "ticker" not in extract_entities("BANANA is bad")


def test_ticker_rejects_non_whitelisted_single_letter_I():
    assert "ticker" not in extract_entities("I like stocks")


def test_ticker_rejects_digits():
    assert "ticker" not in extract_entities("A1B is fake")


# -----------------------------------------------------------------------------
# AC6.3 -- SF 18-char checksum.
# -----------------------------------------------------------------------------


def test_sf_id_valid_checksum():
    assert _validate_sf_id("003xx0000012ABCAA2") is True


def test_sf_id_invalid_checksum():
    assert _validate_sf_id("003xx0000012ABCXXX") is False


def test_sf_id_too_short():
    assert _validate_sf_id("003xx0000012ABC") is False


def test_sf_id_wrong_length():
    assert _validate_sf_id("abc") is False


def test_extract_client_id_positive():
    result = extract_entities("pull up 003xx0000012ABCAA2")
    assert result.get("client_id") == "003xx0000012ABCAA2"


def test_extract_client_id_rejects_bad_checksum():
    assert "client_id" not in extract_entities("pull up 003xx0000012ABCXXX")


# -----------------------------------------------------------------------------
# AC6.4 -- household_id.
# -----------------------------------------------------------------------------


def test_household_id_positive():
    assert (
        extract_entities("HH-A1B2C3D4E5").get("household_id") == "HH-A1B2C3D4E5"
    )


def test_household_id_rejects_lowercase():
    assert "household_id" not in extract_entities("hh-A1B2C3D4E5")


def test_household_id_rejects_too_short():
    assert "household_id" not in extract_entities("HH-123")


# -----------------------------------------------------------------------------
# AC6.5 -- account_id.
# -----------------------------------------------------------------------------


def test_account_id_positive():
    assert extract_entities("ACC-1234ABCD").get("account_id") == "ACC-1234ABCD"


def test_account_id_rejects_lowercase_prefix():
    assert "account_id" not in extract_entities("acc-1234ABCD")


def test_account_id_rejects_too_short():
    assert "account_id" not in extract_entities("ACC-123")


def test_account_id_rejects_wrong_prefix():
    assert "account_id" not in extract_entities("ACCT-1234ABCD")


# -----------------------------------------------------------------------------
# AC6.6 -- date_range absolute + relative.
# -----------------------------------------------------------------------------


def test_date_range_absolute_to():
    result = extract_entities("2026-01-01 to 2026-03-31")
    assert result.get("date_range") == "2026-01-01 to 2026-03-31"


def test_date_range_absolute_em_dash():
    result = extract_entities("2026-01-01 \u2014 2026-03-31")
    assert "date_range" in result


def test_date_range_absolute_rejects_reversed():
    assert "date_range" not in extract_entities("2026-03-31 to 2026-01-01")


def test_date_range_absolute_rejects_invalid_month():
    assert "date_range" not in extract_entities("2026-13-01 to 2026-03-31")


def test_date_range_relative_canonical():
    assert (
        extract_entities("show last quarter").get("date_range") == "last_quarter"
    )
    assert extract_entities("YTD report").get("date_range") == "YTD"
    assert (
        extract_entities("last 30 days report").get("date_range")
        == "last_30_days"
    )


def test_date_range_relative_rejects_unknown():
    assert "date_range" not in extract_entities("last week")


# -----------------------------------------------------------------------------
# AC6.7 -- never raises.
# -----------------------------------------------------------------------------


def test_never_raises_on_weird_input():
    for s in ["", "   ", "\x00\x01\x02", "a" * 10000, "\u0000" * 10]:
        try:
            extract_entities(s)
        except Exception as e:
            raise AssertionError(f"raised on {s!r}: {e}")

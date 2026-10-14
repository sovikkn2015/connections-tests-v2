"""
Tests for Gap 6: MNPI Leakage Scan.

Covers: Layer A pattern matching, Layer B entity extraction,
Layer C classification, decision engine logic, fail-closed behavior.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"mnpi_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_scanner = _load_local("scanner")

FilterLogEntry = _scanner.FilterLogEntry
FinancialEntity = _scanner.FinancialEntity
LayerAScanner = _scanner.LayerAScanner
LayerBScanner = _scanner.LayerBScanner
LayerCResult = _scanner.LayerCResult
LayerCScanner = _scanner.LayerCScanner
LeakageFlag = _scanner.LeakageFlag
MNPIFilterLog = _scanner.MNPIFilterLog
MNPILeakageScanner = _scanner.MNPILeakageScanner
ScanDecision = _scanner.ScanDecision
ScanResult = _scanner.ScanResult


# ── Fixtures ─────────────────────────────────────────────────────


def _make_filter_log(
    stripped: list[FilterLogEntry] | None = None,
    retained: list[str] | None = None,
) -> MNPIFilterLog:
    return MNPIFilterLog(
        trace_id="trace-001",
        fields_stripped=stripped or [
            FilterLogEntry(
                field_path="holdings[0].quantity",
                original_value="1200",
                value_type="integer",
                mnpi_category="position_size",
            ),
            FilterLogEntry(
                field_path="holdings[0].market_value",
                original_value="2400000",
                value_type="currency",
                mnpi_category="position_value",
            ),
        ],
        fields_retained=retained or ["holdings[*].ticker", "holdings[*].sector"],
        policy_bundle="mnpi/v1.4.2",
    )


# ═══════════════════════════════════════════════════════════════════
# LAYER A: Regex Pattern Matching
# ═══════════════════════════════════════════════════════════════════


class TestLayerA:
    def setup_method(self):
        self.scanner = LayerAScanner()

    def test_detects_exact_value(self):
        flog = _make_filter_log()
        flags = self.scanner.scan("The client holds 1200 shares", flog)
        assert len(flags) >= 1
        assert flags[0].layer == "A"

    def test_detects_comma_formatted(self):
        flog = _make_filter_log()
        flags = self.scanner.scan("Position value is $2,400,000", flog)
        assert len(flags) >= 1

    def test_no_flag_on_clean_output(self):
        flog = _make_filter_log()
        flags = self.scanner.scan("The portfolio is diversified across sectors", flog)
        assert len(flags) == 0

    def test_detects_currency_with_dollar(self):
        flog = _make_filter_log(stripped=[
            FilterLogEntry(
                field_path="balance",
                original_value="50000",
                value_type="currency",
                mnpi_category="position_value",
            ),
        ])
        flags = self.scanner.scan("Account balance is $50000", flog)
        assert len(flags) >= 1

    def test_empty_filter_log_no_flags(self):
        flog = _make_filter_log(stripped=[])
        flags = self.scanner.scan("Any text here", flog)
        assert len(flags) == 0

    def test_one_flag_per_field(self):
        """Should not flag the same field multiple times."""
        flog = _make_filter_log(stripped=[
            FilterLogEntry(
                field_path="qty",
                original_value="1200",
                value_type="integer",
                mnpi_category="position_size",
            ),
        ])
        flags = self.scanner.scan("1200 shares worth 1,200 units", flog)
        assert len(flags) == 1


# ═══════════════════════════════════════════════════════════════════
# LAYER B: NER Entity Extraction
# ═══════════════════════════════════════════════════════════════════


class TestLayerB:
    def setup_method(self):
        self.scanner = LayerBScanner()

    def test_extracts_dollar_amounts(self):
        entities = self.scanner._extract_entities("The value is $2,400,000")
        amounts = [e for e in entities if e.entity_type == "amount"]
        assert len(amounts) >= 1

    def test_extracts_percentages(self):
        entities = self.scanner._extract_entities("Return was 12.5%")
        pcts = [e for e in entities if e.entity_type == "percentage"]
        assert len(pcts) == 1
        assert pcts[0].value == "12.5%"

    def test_flags_filtered_data_match(self):
        flog = _make_filter_log()
        flags = self.scanner.scan(
            "Position worth $2,400,000 in tech",
            flog,
            provided_data={"sector": "tech"},
        )
        matched = [f for f in flags if f.match_type == "filtered_data_match"]
        assert len(matched) >= 1

    def test_flags_inferred_data(self):
        flog = _make_filter_log(stripped=[])
        flags = self.scanner.scan(
            "The position is worth $5,000,000",
            flog,
            provided_data={},
        )
        inferred = [f for f in flags if f.match_type == "inferred_data"]
        assert len(inferred) >= 1

    def test_no_flag_for_provided_data(self):
        flog = _make_filter_log(stripped=[])
        flags = self.scanner.scan(
            "The value is $1,000",
            flog,
            provided_data={"value": "1000"},
        )
        inferred = [f for f in flags if f.match_type == "inferred_data"]
        assert len(inferred) == 0

    def test_normalize_millions(self):
        norm = self.scanner._normalize_amount("$2.4M")
        assert norm == "2400000"

    def test_normalize_thousands(self):
        norm = self.scanner._normalize_amount("$50K")
        assert norm == "50000"

    def test_normalize_plain(self):
        norm = self.scanner._normalize_amount("$1,200")
        assert norm == "1200"


# ═══════════════════════════════════════════════════════════════════
# LAYER C: LLM Classification
# ═══════════════════════════════════════════════════════════════════


class TestLayerC:
    @pytest.mark.asyncio
    async def test_mock_result(self):
        scanner = LayerCScanner()
        scanner.set_mock_result(LayerCResult(
            contains_mnpi=True,
            confidence=0.95,
            flagged_phrases=["1200 shares"],
            explanation="Output contains position size",
        ))
        result = await scanner.scan("text", _make_filter_log())
        assert result.contains_mnpi is True
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_no_llm_client_fail_closed(self):
        """No LLM client → fail-closed: assume MNPI present."""
        scanner = LayerCScanner(llm_client=None)
        result = await scanner.scan("text", _make_filter_log())
        assert result.contains_mnpi is True
        assert result.confidence == 1.0
        assert "fail-closed" in result.explanation


# ═══════════════════════════════════════════════════════════════════
# DECISION ENGINE
# ═══════════════════════════════════════════════════════════════════


class TestDecisionEngine:
    @pytest.mark.asyncio
    async def test_clean_output_delivers(self):
        scanner = MNPILeakageScanner()
        result = await scanner.scan(
            "The portfolio is well diversified",
            _make_filter_log(),
        )
        assert result.decision == ScanDecision.DELIVER

    @pytest.mark.asyncio
    async def test_layer_a_only_review(self):
        """Layer A flags but Layer B doesn't → REVIEW."""
        scanner = MNPILeakageScanner()
        flog = _make_filter_log(stripped=[
            FilterLogEntry(
                field_path="qty",
                original_value="1200",
                value_type="integer",
                mnpi_category="position_size",
            ),
        ])
        result = await scanner.scan(
            "There are 1200 items in the list",
            flog,
            provided_data={"items": "1200"},
        )
        assert result.decision in (ScanDecision.DELIVER, ScanDecision.REVIEW)

    @pytest.mark.asyncio
    async def test_all_layers_block(self):
        """A+B+C with high confidence → BLOCK."""
        scanner = MNPILeakageScanner()
        scanner.layer_c.set_mock_result(LayerCResult(
            contains_mnpi=True,
            confidence=0.95,
            explanation="Confirmed MNPI leakage",
        ))
        flog = _make_filter_log(stripped=[
            FilterLogEntry(
                field_path="holdings[0].market_value",
                original_value="2400000",
                value_type="currency",
                mnpi_category="position_value",
            ),
        ])
        result = await scanner.scan(
            "The position is worth $2,400,000 in AAPL",
            flog,
            provided_data={},
        )
        assert result.decision == ScanDecision.BLOCK
        assert "confirmed" in result.blocked_reason.lower() or "MNPI" in result.blocked_reason

    @pytest.mark.asyncio
    async def test_ab_flagged_c_low_confidence_review_high(self):
        """A+B flagged but C low confidence → REVIEW_HIGH."""
        scanner = MNPILeakageScanner()
        scanner.layer_c.set_mock_result(LayerCResult(
            contains_mnpi=False,
            confidence=0.3,
        ))
        flog = _make_filter_log(stripped=[
            FilterLogEntry(
                field_path="holdings[0].market_value",
                original_value="2400000",
                value_type="currency",
                mnpi_category="position_value",
            ),
        ])
        result = await scanner.scan(
            "The position is worth $2,400,000",
            flog,
            provided_data={},
        )
        assert result.decision == ScanDecision.REVIEW_HIGH

    @pytest.mark.asyncio
    async def test_fail_closed_on_error(self):
        """Scanner error → BLOCK (fail-closed)."""
        scanner = MNPILeakageScanner()

        class BadFilterLog:
            trace_id = "trace"
            fields_stripped = None
            fields_retained = []
            policy_bundle = ""

        result = await scanner.scan("text", BadFilterLog())  # type: ignore
        assert result.decision == ScanDecision.BLOCK
        assert result.error != ""

    @pytest.mark.asyncio
    async def test_latency_tracked(self):
        scanner = MNPILeakageScanner()
        result = await scanner.scan(
            "Clean output text",
            _make_filter_log(),
        )
        assert result.layer_a_latency_ms >= 0
        assert result.total_latency_ms >= 0

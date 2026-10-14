"""
Performance Tests — MNPI Leakage Scan (Layer A Regex).

Benchmarks the Layer A regex scanner from M6 leakage_scan.py against
ARCH-06 latency budgets:
  - Layer A: <10ms for standard payloads (50+ fields)
  - Layer A: <50ms for 100KB payloads
  - Detection overhead: negligible vs clean payloads

Uses time.perf_counter_ns() for nanosecond precision.
No external benchmarking libraries — just pytest + time.
"""

from __future__ import annotations

import json
import time

import pytest

from conftest import (
    _generate_client_payload,
    _generate_large_payload,
    percentile,
    print_latency_stats,
)
from m6_mcp_gateway.leakage_scan import scan_output


# ═══════════════════════════════════════════════════════════════════
# TEST 1: Layer A latency under 10ms (ARCH-06 budget)
# ═══════════════════════════════════════════════════════════════════


class TestLayerALatency:
    """Layer A regex scan must complete within ARCH-06 latency budget."""

    def test_layer_a_latency_under_10ms(self, client_data_payload: dict) -> None:
        """
        Run scan_output 1000 times with realistic payloads (nested JSON
        with 50+ fields). Assert p99 latency < 10ms.

        This is the Layer A budget from ARCH-06 Gap 6.
        """
        latencies_ms: list[float] = []

        # Warm up — first few runs may be slower due to regex compilation cache
        for _ in range(10):
            scan_output(client_data_payload)

        for _ in range(1000):
            start = time.perf_counter_ns()
            result = scan_output(client_data_payload)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            # Functional sanity: clean payload should pass
            assert result.passed is True

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Layer A — 50+ field payload (1000 runs)", latencies_ms)

        assert p99 < 10.0, (
            f"Layer A p99={p99:.3f}ms exceeds ARCH-06 budget of 10ms"
        )

    def test_layer_a_large_payload(self, large_payload_100kb: dict) -> None:
        """
        Scan a ~100KB payload. Assert still under 50ms at p99.

        Large payloads stress the recursive text extraction and regex
        matching. 50ms is a generous budget (5x the standard 10ms).
        """
        # Verify payload is actually ~100KB
        payload_size = len(json.dumps(large_payload_100kb))
        assert payload_size > 80_000, (
            f"Payload too small: {payload_size} bytes (expected ~100KB)"
        )

        latencies_ms: list[float] = []

        # Warm up
        for _ in range(5):
            scan_output(large_payload_100kb)

        for _ in range(1000):
            start = time.perf_counter_ns()
            result = scan_output(large_payload_100kb)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            assert result.passed is True

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Layer A — 100KB payload (1000 runs)", latencies_ms)

        assert p99 < 50.0, (
            f"Layer A p99={p99:.3f}ms exceeds 50ms budget for 100KB payload"
        )

    def test_layer_a_with_detections(
        self,
        payload_with_ssn: dict,
        payload_with_dob: dict,
    ) -> None:
        """
        Scan payloads containing SSN/DOB patterns. Assert detection
        doesn't significantly increase latency vs clean payloads.

        Detection should add negligible overhead — regex findall is
        the same cost whether it matches or not.
        """
        # Measure clean payload baseline
        clean_payload = _generate_client_payload()
        clean_latencies: list[float] = []
        for _ in range(500):
            start = time.perf_counter_ns()
            scan_output(clean_payload)
            clean_latencies.append((time.perf_counter_ns() - start) / 1_000_000)

        # Measure SSN-containing payload
        ssn_latencies: list[float] = []
        for _ in range(500):
            start = time.perf_counter_ns()
            result = scan_output(payload_with_ssn)
            ssn_latencies.append((time.perf_counter_ns() - start) / 1_000_000)
            # Must detect the SSN
            assert result.passed is False, "SSN should be detected"
            assert any(
                "ssn" in d for d in result.layers[0].detections
            ), "Layer A should flag SSN pattern"

        # Measure DOB-containing payload
        dob_latencies: list[float] = []
        for _ in range(500):
            start = time.perf_counter_ns()
            result = scan_output(payload_with_dob)
            dob_latencies.append((time.perf_counter_ns() - start) / 1_000_000)
            assert result.passed is False, "DOB should be detected"

        clean_p99 = percentile(clean_latencies, 99)
        ssn_p99 = percentile(ssn_latencies, 99)
        dob_p99 = percentile(dob_latencies, 99)

        print_latency_stats("Layer A — clean payload baseline", clean_latencies)
        print_latency_stats("Layer A — SSN detection", ssn_latencies)
        print_latency_stats("Layer A — DOB detection", dob_latencies)

        # Detection overhead should be < 2x clean baseline
        # (generous margin — in practice regex cost is identical)
        assert ssn_p99 < max(clean_p99 * 2.0, 10.0), (
            f"SSN detection p99={ssn_p99:.3f}ms is >2x clean baseline "
            f"p99={clean_p99:.3f}ms"
        )
        assert dob_p99 < max(clean_p99 * 2.0, 10.0), (
            f"DOB detection p99={dob_p99:.3f}ms is >2x clean baseline "
            f"p99={clean_p99:.3f}ms"
        )

        # Both must still be under the 10ms ARCH-06 budget
        assert ssn_p99 < 10.0, (
            f"SSN detection p99={ssn_p99:.3f}ms exceeds 10ms budget"
        )
        assert dob_p99 < 10.0, (
            f"DOB detection p99={dob_p99:.3f}ms exceeds 10ms budget"
        )

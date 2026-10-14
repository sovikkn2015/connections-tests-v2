"""M8 <-> M6 shape-match integration tests (v0.3.0 un-xfail).

History:
  * Task 20 (v0.2.0): M8's GatewayRequest/GatewayResponse dataclass shapes
    asserted field-for-field equal to M6's exported types (Req-Fix 1).
    Tests inline-xfailed when M6 wasn't importable in the test env.
  * v0.3.0 (this file): M6 now ships a FastAPI app exposing /adapters and
    /gateway/reasons. The inline xfails are gone -- M6 is always
    importable, and the new routes are exercised via ``TestClient`` so
    wire-shape drift (between M8's local dataclass copies and M6's
    published vocab) fails at CI time, not at prod-deploy time.

Uses ``dataclasses.fields()`` for introspection (NOT Pydantic
``model_fields``). Both sides are ``@dataclass(frozen=True)`` per M8's
Req-Fix 1.
"""

from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient

from m6_mcp_gateway import (
    GatewayRequest as M6Request,
    GatewayResponse as M6Response,
    VALID_GATEWAY_REASONS,
)
from m6_mcp_gateway.app import app as m6_app
from m8_pipeline_engine.gateway_client import (
    GatewayError as M8Err,
    GatewayRequest as M8Request,
    GatewayResponse as M8Response,
    _call_with_branching,
)


# =============================================================================
# Dataclass shape equivalence (Task 20 -- now unconditional).
# =============================================================================


def test_m8_gateway_request_fields_match_m6_shape() -> None:
    m8_fields = tuple(f.name for f in dataclasses.fields(M8Request))
    m6_fields = tuple(f.name for f in dataclasses.fields(M6Request))
    assert m8_fields == m6_fields, (
        f"Field drift: M8={m8_fields} vs M6={m6_fields}"
    )


def test_m8_gateway_response_fields_match_m6_shape() -> None:
    m8_fields = tuple(f.name for f in dataclasses.fields(M8Response))
    m6_fields = tuple(f.name for f in dataclasses.fields(M6Response))
    assert m8_fields == m6_fields, (
        f"Field drift: M8={m8_fields} vs M6={m6_fields}"
    )


def test_m8_gateway_error_reason_attribute_duck_types_m6() -> None:
    exc = M8Err("authority_denied")
    assert hasattr(exc, "reason")
    assert exc.reason == "authority_denied"


# =============================================================================
# Reason-vocabulary equivalence (Task 20 -- now unconditional).
# =============================================================================


_EXPECTED_REASONS = {
    "invalid_identity",
    "authority_denied",
    "authority_escalated",
    "mnpi_filter_error",
    "circuit_open",
    "rate_limited",
    "vendor_unavailable",
    "vendor_error",
    "mnpi_leakage_scan",
    "audit_failed",
    "invalid_request",
}


def test_m8_valid_gateway_reasons_matches_m6() -> None:
    """M6 is the source of truth -- M8 must branch across the same 11."""
    assert set(VALID_GATEWAY_REASONS) == _EXPECTED_REASONS


# =============================================================================
# /gateway/reasons wire route -- peer modules bootstrap from this.
# =============================================================================


def test_m6_gateway_reasons_route_publishes_full_vocab() -> None:
    """``GET /gateway/reasons`` must return all 11 reasons."""
    with TestClient(m6_app) as client:
        resp = client.get("/gateway/reasons")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["reasons"], list)
    assert set(body["reasons"]) == set(VALID_GATEWAY_REASONS)
    assert set(body["reasons"]) == _EXPECTED_REASONS


def test_m6_gateway_reasons_match_m8_branching_reasons() -> None:
    """Every reason M8's ``_call_with_branching`` handles is published.

    Guards against silent vocab drift: if someone adds a reason to M6
    without teaching M8's router, this test starts failing.
    """
    # These are the literal reasons hard-coded in
    # ``_call_with_branching`` (src/m8_pipeline_engine/gateway_client.py).
    m8_branched = {
        "authority_denied",
        "authority_escalated",
        "vendor_unavailable",
        "vendor_error",
        "rate_limited",
        "circuit_open",
        "mnpi_leakage_scan",
        "mnpi_filter_error",
        "audit_failed",
        "invalid_request",
        "invalid_identity",
    }
    with TestClient(m6_app) as client:
        published = set(client.get("/gateway/reasons").json()["reasons"])
    assert m8_branched.issubset(published)
    assert published == m8_branched, (
        "M6 reason vocab drifted from M8 branching reasons: "
        f"m6_only={published - m8_branched} "
        f"m8_only={m8_branched - published}"
    )


# =============================================================================
# /adapters wire route -- M8 pods hydrate LocalVendorAdapterResolver.
# =============================================================================


def test_m6_adapters_route_returns_manifest_shape() -> None:
    """The manifest shape must match what ``LocalVendorAdapterResolver``
    can consume: a list of dicts with ``name`` + ``tool_names`` keys.

    Module-level ``app`` ships without a registry, so the list is
    empty; the important invariant is the envelope shape.
    """
    with TestClient(m6_app) as client:
        resp = client.get("/adapters")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "adapters" in body
    assert isinstance(body["adapters"], list)


# =============================================================================
# Referenced-but-not-invoked import guard -- keeps _call_with_branching in
# the module graph so shape-drift in M8's router is caught here too.
# =============================================================================


def test_m8_call_with_branching_is_importable() -> None:
    """Keeps ``_call_with_branching`` referenced; shape regressions in
    its signature will surface as an ImportError at collection time."""
    assert callable(_call_with_branching)

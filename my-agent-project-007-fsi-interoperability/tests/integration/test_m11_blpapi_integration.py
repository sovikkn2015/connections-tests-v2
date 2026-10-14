"""M11 BLPAPI integration tests.

Record-and-replay: fixtures under `tests/fixtures/bloomberg/` feed the
`FakeBlpapiClient`, which is mounted through the full bootstrap + FastAPI
stack. Every test exercises the end-to-end MCP contract:

    HTTP POST /tools/call → FastAPI → pydantic validate → tool handler →
    BloombergRefDataClient → session pool → FakeBlpapiClient (fixture)

No live Bloomberg. No Terminal required.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from m11_blpapi_adapters.bloomberg_refdata.src.client import (
    BloombergRefDataClient,
    BloombergSessionPool,
    FakeBlpapiClient,
)
from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiResponse,
    BlpapiVendorError,
)
from m11_blpapi_adapters.bloomberg_refdata.src.server import create_app


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "bloomberg"


async def _build_app_with_fake(fake: FakeBlpapiClient):
    from m11_blpapi_adapters.bloomberg_refdata.src.config import BlpapiConfig

    cfg = BlpapiConfig(
        enabled=True,
        host="localhost",
        port=8194,
        uuid_vault_path="secret/data/007/m11-blpapi/uuid",
        serial_vault_path="secret/data/007/m11-blpapi/serial",
        client_mode="DAPI",
        session_timeout_ms=30_000,
        circuit_threshold=5,
        circuit_cooldown_ms=30_000,
        rate_limit_rpm=60_000,
        rate_limit_burst=500,
        fixtures_dir=str(FIXTURES_DIR),
        secrets_backend="fake",
        http_port=8080,
        log_level="info",
    )
    # Pre-seed the fake Vault with values so `enabled=True` bootstrap succeeds.
    from m11_python_adapters_shared import FakeVaultClient
    vault = FakeVaultClient(
        {
            cfg.uuid_vault_path: "123456789",
            cfg.serial_vault_path: "TS-42",
        }
    )
    app, result = await create_app(
        config=cfg, blpapi_client=fake, secrets=vault
    )
    return app, result


def _load_fixture(filename: str) -> dict:
    with (FIXTURES_DIR / filename).open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# MCP contract — GET / + POST /tools/list + POST /tools/call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_mcp_contract_endpoints() -> None:
    fake = FakeBlpapiClient()
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    # GET / — server info + health. Must return 200 + expected keys.
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "m11-blpapi-adapter"
    assert body["vendor"] == "bloomberg"
    assert body["status"] in {"ok", "degraded"}
    assert "bloomberg.reference_data" in body["capabilities"]["tools"]

    # POST /tools/list — every tool shows up with a populated inputSchema.
    r = client.post("/tools/list")
    assert r.status_code == 200
    listed = r.json()
    names = {t["name"] for t in listed["tools"]}
    assert names == {
        "bloomberg.reference_data",
        "bloomberg.historical_data",
        "bloomberg.intraday_tick",
        "bloomberg.corporate_actions",
    }
    for t in listed["tools"]:
        assert "inputSchema" in t
        assert t["inputSchema"]["type"] == "object"
        assert t["inputSchema"].get("additionalProperties") is False


# ---------------------------------------------------------------------------
# Reference data happy-path via fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_reference_data_happy_path() -> None:
    fake = FakeBlpapiClient()
    fx = _load_fixture("reference_data_aapl_basic.json")
    fake.set_default_response(
        BlpapiResponse(
            data=fx["data"],
            partial=fx["partial"],
            vendor_response_code=fx["vendor_response_code"],
        )
    )
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.reference_data",
            "arguments": {
                "securities": [
                    {"identifier_type": "TICKER", "value": "AAPL US Equity"}
                ],
                "fields": ["PX_LAST", "MKT_CAP", "INDUSTRY_SECTOR"],
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is False
    sec_data = body["content"]["data"]["ReferenceDataResponse"]["securityData"][0]
    assert sec_data["security"] == "AAPL US Equity"
    assert sec_data["fieldData"]["PX_LAST"] == 189.46


# ---------------------------------------------------------------------------
# Historical data w/ adjustment flags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_historical_data_with_split_adjustment() -> None:
    fake = FakeBlpapiClient()
    fx = _load_fixture("historical_data_aapl_5y.json")
    fake.set_default_response(BlpapiResponse(data=fx["data"]))
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.historical_data",
            "arguments": {
                "securities": [
                    {"identifier_type": "TICKER", "value": "AAPL US Equity"}
                ],
                "fields": ["PX_LAST", "VOLUME"],
                "start_date": "2020-01-01",
                "end_date": "2020-01-07",
                "adjustment_split": True,
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    rows = body["content"]["data"]["HistoricalDataResponse"]["securityData"][
        "fieldDataArray"
    ]
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Intraday tick
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_intraday_tick_window() -> None:
    fake = FakeBlpapiClient()
    fx = _load_fixture("intraday_tick_aapl_window.json")
    fake.set_default_response(BlpapiResponse(data=fx["data"]))
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.intraday_tick",
            "arguments": {
                "security": {
                    "identifier_type": "TICKER",
                    "value": "AAPL US Equity",
                },
                "event_types": ["TRADE", "BID", "ASK"],
                "start_datetime": "2026-05-20T13:30:00+00:00",
                "end_datetime": "2026-05-20T14:00:00+00:00",
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    ticks = body["content"]["data"]["IntradayTickResponse"]["tickData"]
    assert len(ticks) == 3
    assert {t["type"] for t in ticks} == {"TRADE", "BID", "ASK"}


# ---------------------------------------------------------------------------
# Corporate actions multi-year
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_corporate_actions_multi_year() -> None:
    fake = FakeBlpapiClient()
    fx = _load_fixture("corporate_actions_msft_3y.json")
    fake.set_default_response(BlpapiResponse(data=fx["data"]))
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.corporate_actions",
            "arguments": {
                "securities": [
                    {"identifier_type": "TICKER", "value": "MSFT US Equity"}
                ],
                "action_types": ["DVD_CASH"],
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    divs = body["content"]["data"]["ReferenceDataResponse"]["securityData"][0][
        "fieldData"
    ]["DVD_HIST_ALL"]
    assert len(divs) == 4


# ---------------------------------------------------------------------------
# Error translation via the MCP envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_not_entitled_returns_mcp_error_envelope() -> None:
    fake = FakeBlpapiClient()
    fake.set_default_error(BlpapiVendorError("NOT_ENTITLED", "not licensed"))
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.reference_data",
            "arguments": {
                "securities": [
                    {"identifier_type": "TICKER", "value": "AAPL US Equity"}
                ],
                "fields": ["EARNINGS_ESTIMATE"],
            },
        },
    )
    # HTTP 200 — the envelope carries the error signal.
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is True
    assert body["errorCode"] == "vendor_not_entitled"
    assert body["retryable"] is False
    assert body["vendorStatusCode"] == "NOT_ENTITLED"


@pytest.mark.asyncio
async def test_integration_invalid_arguments_returns_envelope() -> None:
    fake = FakeBlpapiClient()
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    # Lowercase field is invalid (Bloomberg fields are upper-case).
    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={
            "name": "bloomberg.reference_data",
            "arguments": {
                "securities": [
                    {"identifier_type": "TICKER", "value": "AAPL US Equity"}
                ],
                "fields": ["px_last"],
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is True
    assert body["errorCode"] == "invalid_arguments"


@pytest.mark.asyncio
async def test_integration_unknown_tool_returns_envelope() -> None:
    fake = FakeBlpapiClient()
    app, _ = await _build_app_with_fake(fake)
    client = TestClient(app)

    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "firm_abc"},
        json={"name": "bloomberg.nope", "arguments": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is True
    assert body["errorCode"] == "invalid_arguments"


# ---------------------------------------------------------------------------
# Session-pool stress — 100 concurrent calls still serialize to 1 session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_session_pool_stress_100_concurrent() -> None:
    fake = FakeBlpapiClient()
    fake.set_default_response(BlpapiResponse(data={"ok": True}))
    fake.set_latency_ms(1)  # microseconds of imagined I/O

    # Drive the stress test at the client level (bypassing FastAPI) so we can
    # use asyncio.gather directly; the Starlette TestClient runs each call
    # synchronously.
    await fake.open()
    pool = BloombergSessionPool(fake)
    import io
    from m11_python_adapters_shared import (
        AuditEmitter,
        CircuitBreaker,
        FakeClock,
        RateLimiter,
    )
    clock = FakeClock()
    ae = AuditEmitter(logger=None, stream=io.StringIO())
    breaker = CircuitBreaker(clock, threshold=100, cooldown_ms=1000)
    rl = RateLimiter(clock, rpm=600_000, burst=500)
    refclient = BloombergRefDataClient(
        pool=pool, audit=ae, breaker=breaker, rate_limiter=rl, clock=clock
    )
    await refclient.open()

    from m11_blpapi_adapters.bloomberg_refdata.src.models import (
        ReferenceDataInput,
        SecurityRef,
    )
    import asyncio

    async def one() -> None:
        await refclient.reference_data(
            ReferenceDataInput(
                securities=[SecurityRef(identifier_type="TICKER", value="AAPL US Equity")],
                fields=["PX_LAST"],
            ),
            "firm1",
        )

    await asyncio.gather(*[one() for _ in range(100)])
    assert fake.max_concurrent == 1
    assert len(fake.call_log) == 100
    await refclient.shutdown()

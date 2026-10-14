"""M11 gRPC (ICE Data) integration tests.

Full FastAPI round-trip via TestClient. Uses :class:`FakeIceStub` as the
gRPC backend — no live ICE Data endpoint needed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from m11_grpc_adapters.ice_data.src.client import FakeIceStub
from m11_grpc_adapters.ice_data.src.client.protocol import IceVendorError
from m11_grpc_adapters.ice_data.src.config import IceConfig
from m11_grpc_adapters.ice_data.src.server import create_app
from m11_python_adapters_shared import FakeVaultClient


async def _build_app_with_fake(stub: FakeIceStub):
    cfg = IceConfig(
        enabled=True,
        target="localhost:50051",
        tenant_id="default-tenant",
        bearer_token_vault_path="secret/data/007/m11-grpc/bearer",
        mtls_cert_vault_path="secret/data/007/m11-grpc/mtls/cert",
        mtls_key_vault_path="secret/data/007/m11-grpc/mtls/key",
        mtls_ca_vault_path="secret/data/007/m11-grpc/mtls/ca",
        channel_pool_size=4,
        channel_idle_s=300,
        circuit_threshold=5,
        circuit_cooldown_ms=30_000,
        rate_limit_rpm=600_000,
        rate_limit_burst=500,
        secrets_backend="fake",
        fixtures_dir="/tmp",
        http_port=8080,
        log_level="info",
    )
    vault = FakeVaultClient(
        {
            cfg.bearer_token_vault_path: "fake-token",
            cfg.mtls_cert_vault_path: "-----FAKE CERT-----",
            cfg.mtls_key_vault_path: "-----FAKE KEY-----",
            cfg.mtls_ca_vault_path: "-----FAKE CA-----",
        }
    )
    app, result = await create_app(config=cfg, stub=stub, secrets=vault)
    return app, result


@pytest.mark.asyncio
async def test_grpc_mcp_contract_endpoints() -> None:
    stub = FakeIceStub()
    app, _ = await _build_app_with_fake(stub)
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "m11-grpc-adapter"
    assert body["vendor"] == "ice_data"

    r = client.post("/tools/list")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert names == {
        "ice.market_data_snapshot",
        "ice.trade_tape",
        "ice.reference_data",
    }
    for t in r.json()["tools"]:
        assert t["inputSchema"]["type"] == "object"
        assert t["inputSchema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_grpc_market_data_snapshot_happy() -> None:
    stub = FakeIceStub()
    app, result = await _build_app_with_fake(stub)
    # Bootstrap opens the default tenant; we set the response there.
    stub.set_response(
        "get_market_data_snapshot",
        None,
        {"quotes": [{"symbol": "SPY", "bid": 450.1, "ask": 450.12}]},
    )
    client = TestClient(app)
    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "default-tenant"},
        json={
            "name": "ice.market_data_snapshot",
            "arguments": {
                "securities": [
                    {"identifier_type": "SYMBOL", "value": "SPY", "venue": "ARCA"}
                ],
                "include_depth": False,
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is False
    assert body["content"]["quotes"][0]["symbol"] == "SPY"


@pytest.mark.asyncio
async def test_grpc_trade_tape_happy() -> None:
    stub = FakeIceStub()
    app, _ = await _build_app_with_fake(stub)
    stub.set_response(
        "get_trade_tape",
        None,
        {"ticks": [{"price": 450.0, "size": 100, "timestamp_us": 1_700_000_000_000_000}]},
    )
    client = TestClient(app)
    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "default-tenant"},
        json={
            "name": "ice.trade_tape",
            "arguments": {
                "security": {
                    "identifier_type": "SYMBOL",
                    "value": "SPY",
                    "venue": "ARCA",
                },
                "start_time": "2026-05-20T13:30:00+00:00",
                "end_time": "2026-05-20T20:00:00+00:00",
                "max_ticks": 1000,
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["content"]["ticks"]) == 1


@pytest.mark.asyncio
async def test_grpc_reference_data_happy() -> None:
    stub = FakeIceStub()
    app, _ = await _build_app_with_fake(stub)
    stub.set_response(
        "get_reference_data",
        None,
        {"securities": [{"asset_class": "ETF", "tick_size": "0.01"}]},
    )
    client = TestClient(app)
    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "default-tenant"},
        json={
            "name": "ice.reference_data",
            "arguments": {
                "securities": [
                    {"identifier_type": "SYMBOL", "value": "SPY", "venue": "ARCA"}
                ],
                "as_of_date": "2026-05-20",
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["content"]["securities"][0]["asset_class"] == "ETF"


@pytest.mark.asyncio
async def test_grpc_unavailable_returns_canonical_envelope() -> None:
    stub = FakeIceStub()
    app, _ = await _build_app_with_fake(stub)
    stub.set_error(
        "get_market_data_snapshot",
        None,
        IceVendorError("PERMISSION_DENIED", "entitlement missing"),
    )
    client = TestClient(app)
    r = client.post(
        "/tools/call",
        headers={"X-Firm-ID": "default-tenant"},
        json={
            "name": "ice.market_data_snapshot",
            "arguments": {
                "securities": [
                    {"identifier_type": "SYMBOL", "value": "SPY", "venue": "ARCA"}
                ]
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["isError"] is True
    assert body["errorCode"] == "vendor_not_entitled"
    assert body["retryable"] is False
    assert body["vendorStatusCode"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_grpc_graceful_shutdown_closes_channels() -> None:
    stub = FakeIceStub()
    app, result = await _build_app_with_fake(stub)
    stub.set_response("get_market_data_snapshot", None, {"quotes": []})
    client = TestClient(app)
    client.post(
        "/tools/call",
        headers={"X-Firm-ID": "default-tenant"},
        json={
            "name": "ice.market_data_snapshot",
            "arguments": {
                "securities": [
                    {"identifier_type": "SYMBOL", "value": "SPY", "venue": "ARCA"}
                ]
            },
        },
    )
    assert stub.open_count == 1
    await result.client.shutdown()
    assert stub.close_count == 1

"""Bootstrap + SIGTERM wiring for the ICE Data gRPC adapter."""

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Any, Mapping

from m11_grpc_adapters.ice_data.src.client import (
    FakeIceStub,
    IceChannelPool,
    IceDataClient,
    IceStubProtocol,
)
from m11_grpc_adapters.ice_data.src.config import IceConfig, load_config
from m11_grpc_adapters.ice_data.src.tools import build_tools
from m11_python_adapters_shared import (
    AuditEmitter,
    CircuitBreaker,
    FakeVaultClient,
    HealthStatus,
    RateLimiter,
    SecretsClientProtocol,
    ServerInfo,
    SystemClock,
    ToolDefinition,
    get_logger,
)


@dataclass(frozen=True)
class BootstrapResult:
    config: IceConfig
    client: IceDataClient
    stub: IceStubProtocol
    pool: IceChannelPool
    tools: Mapping[str, ToolDefinition]
    info: ServerInfo
    health: Any


async def bootstrap(
    *,
    config: IceConfig | None = None,
    stub: IceStubProtocol | None = None,
    secrets: SecretsClientProtocol | None = None,
    audit: AuditEmitter | None = None,
) -> BootstrapResult:
    cfg = config if config is not None else load_config()
    logger = get_logger(
        adapter_name="m11-grpc-adapter",
        vendor="ice_data",
        level=cfg.log_level,
    )

    sc = secrets
    if sc is None:
        sc = FakeVaultClient()

    if cfg.enabled and stub is None:
        # Resolve mTLS + bearer from Vault. Bytes are expected by grpc SSL creds.
        token = await sc.get_secret(cfg.bearer_token_vault_path)
        cert = (await sc.get_secret(cfg.mtls_cert_vault_path)).encode("utf-8")
        key = (await sc.get_secret(cfg.mtls_key_vault_path)).encode("utf-8")
        ca = (await sc.get_secret(cfg.mtls_ca_vault_path)).encode("utf-8")
        # Lazy-import the real stub to avoid importing grpc at the top of this
        # module; the fake suite never reaches this branch.
        from m11_grpc_adapters.ice_data.src.client.real_stub import RealIceStub

        stub = RealIceStub(
            target=cfg.target,
            mtls_cert=cert,
            mtls_key=key,
            mtls_ca=ca,
            bearer_token=token,
            pool_size=cfg.channel_pool_size,
        )

    if stub is None:
        stub = FakeIceStub()

    pool = IceChannelPool(stub)
    ae = audit if audit is not None else AuditEmitter(logger=logger)
    clock = SystemClock()
    breaker = CircuitBreaker(
        clock,
        threshold=cfg.circuit_threshold,
        cooldown_ms=cfg.circuit_cooldown_ms,
    )
    rate_limiter = RateLimiter(
        clock,
        rpm=cfg.rate_limit_rpm,
        burst=cfg.rate_limit_burst,
    )
    client = IceDataClient(
        pool=pool,
        tenant_id=cfg.tenant_id,
        audit=ae,
        breaker=breaker,
        rate_limiter=rate_limiter,
        clock=clock,
        logger=logger,
        enabled=cfg.enabled,
    )
    await client.open()
    tools = build_tools(client)

    info = ServerInfo(
        name="m11-grpc-adapter",
        version="0.1.0",
        vendor="ice_data",
        capabilities={
            "tools": list(tools.keys()),
            "ice_enabled": cfg.enabled,
            "target": cfg.target if cfg.enabled else "(disabled)",
        },
    )

    async def health() -> HealthStatus:
        if not cfg.enabled:
            return HealthStatus(ok=True, checks={"ice": "disabled"})
        return HealthStatus(
            ok=client.healthy(),
            checks={
                "ice": "ok" if client.healthy() else "degraded",
                "breaker": breaker.state.value,
            },
        )

    return BootstrapResult(
        config=cfg,
        client=client,
        stub=stub,
        pool=pool,
        tools=tools,
        info=info,
        health=health,
    )


def install_sigterm_handler(
    result: BootstrapResult,
    *,
    loop: Any | None = None,
) -> None:
    import asyncio

    loop = loop or asyncio.get_event_loop()

    def _handler() -> None:
        asyncio.ensure_future(result.client.shutdown(), loop=loop)

    try:
        loop.add_signal_handler(signal.SIGTERM, _handler)
        loop.add_signal_handler(signal.SIGINT, _handler)
    except NotImplementedError:  # pragma: no cover
        return

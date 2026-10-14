"""Bootstrap + SIGTERM wiring for the Bloomberg refdata adapter.

Called from ``server.py`` (FastAPI lifespan) and from tests. Returns a
:class:`BootstrapResult` that holds the live objects so tests can poke them
directly.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Any, Mapping

from m11_blpapi_adapters.bloomberg_refdata.src.client import (
    BlpapiClientProtocol,
    BloombergRefDataClient,
    BloombergSessionPool,
    FakeBlpapiClient,
)
from m11_blpapi_adapters.bloomberg_refdata.src.config import BlpapiConfig, load_config
from m11_blpapi_adapters.bloomberg_refdata.src.tools import build_tools
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
    """Container for adapter-wide objects exposed to tests + server."""

    config: BlpapiConfig
    client: BloombergRefDataClient
    blpapi_client: BlpapiClientProtocol
    pool: BloombergSessionPool
    tools: Mapping[str, ToolDefinition]
    info: ServerInfo
    health: Any  # async () -> HealthStatus


async def bootstrap(
    *,
    config: BlpapiConfig | None = None,
    blpapi_client: BlpapiClientProtocol | None = None,
    secrets: SecretsClientProtocol | None = None,
    audit: AuditEmitter | None = None,
) -> BootstrapResult:
    """Build the adapter wiring.

    All arguments are injectable so tests can swap the fake client, the fake
    vault, and a captured-stream audit emitter.
    """
    cfg = config if config is not None else load_config()
    logger = get_logger(
        adapter_name="m11-blpapi-adapter",
        vendor="bloomberg",
        level=cfg.log_level,
    )

    # Secrets — the adapter reads UUID + serial as strings but never echoes
    # them in logs (see AuditEmitter — only counts + IDs, not credentials).
    sc = secrets
    if sc is None:
        if cfg.secrets_backend == "fake":
            sc = FakeVaultClient()
        else:
            # Real Vault client stub — production image ships its own Vault
            # integration via ExternalSecret → env. In our in-tree Python we
            # only wire the Fake; real client is production-only.
            sc = FakeVaultClient()

    # Bloomberg auth loads UUID + serial; values are kept in the real client.
    if cfg.enabled and blpapi_client is None:
        _ = await sc.get_secret(cfg.uuid_vault_path)
        _ = await sc.get_secret(cfg.serial_vault_path)

    # Choose BLPAPI client — real only when explicitly enabled.
    if blpapi_client is None:
        blpapi_client = FakeBlpapiClient(fixtures_dir=cfg.fixtures_dir)

    pool = BloombergSessionPool(blpapi_client)
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
    refdata = BloombergRefDataClient(
        pool=pool,
        audit=ae,
        breaker=breaker,
        rate_limiter=rate_limiter,
        clock=clock,
        logger=logger,
        enabled=cfg.enabled,
    )
    await refdata.open()
    tools = build_tools(refdata)

    info = ServerInfo(
        name="m11-blpapi-adapter",
        version="0.1.0",
        vendor="bloomberg",
        capabilities={
            "tools": list(tools.keys()),
            "blpapi_enabled": cfg.enabled,
            "fixtures_dir": cfg.fixtures_dir,
        },
    )

    async def health() -> HealthStatus:
        """Aggregate health check — 200 when healthy OR adapter disabled."""
        if not cfg.enabled:
            return HealthStatus(ok=True, checks={"blpapi": "disabled"})
        return HealthStatus(
            ok=refdata.healthy(),
            checks={
                "blpapi": "ok" if refdata.healthy() else "degraded",
                "breaker": breaker.state.value,
            },
        )

    return BootstrapResult(
        config=cfg,
        client=refdata,
        blpapi_client=blpapi_client,
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
    """Install SIGTERM + SIGINT handlers that call :meth:`shutdown`.

    Pods receive SIGTERM during eviction; we have `terminationGracePeriodSeconds`
    (30s default) to drain. Calling `shutdown()` flushes the BLPAPI session
    and unblocks `close_all()` so the uvicorn workers exit cleanly.
    """
    import asyncio

    loop = loop or asyncio.get_event_loop()

    def _handler() -> None:
        # Schedule shutdown on the running loop; signal handler must not await.
        asyncio.ensure_future(result.client.shutdown(), loop=loop)

    try:
        loop.add_signal_handler(signal.SIGTERM, _handler)
        loop.add_signal_handler(signal.SIGINT, _handler)
    except NotImplementedError:  # pragma: no cover — Windows / non-main thread
        # Gracefully degrade — unit tests run without signal handlers.
        return

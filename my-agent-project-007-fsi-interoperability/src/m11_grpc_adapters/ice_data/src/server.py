"""FastAPI MCP server entry point for ICE Data gRPC adapter."""

from __future__ import annotations

import asyncio
from typing import Any

from m11_grpc_adapters.ice_data.src.startup import BootstrapResult, bootstrap
from m11_python_adapters_shared import build_app


async def create_app(**bootstrap_kwargs: Any) -> tuple[Any, BootstrapResult]:
    result = await bootstrap(**bootstrap_kwargs)
    app = build_app(result.info, result.tools, result.health)
    return app, result


def create_app_sync() -> Any:
    loop = asyncio.new_event_loop()
    try:
        app, _ = loop.run_until_complete(create_app())
        return app
    finally:
        loop.close()

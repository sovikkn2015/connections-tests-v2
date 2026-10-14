"""FastAPI MCP server entry point.

Called by ``python -m m11_blpapi_adapters.bloomberg_refdata`` (see
``__main__.py``). Also imported by the production Docker ENTRYPOINT via
``uvicorn m11_blpapi_adapters.bloomberg_refdata.src.server:app``.

The server module deliberately provides both:

* :func:`create_app` — factory that returns a FastAPI instance with the
  adapter wiring. Tests call this with an injected fake client.
* ``app`` — module-level instance built at import time from env config. This
  is what uvicorn consumes as ``--factory`` is unnecessary at runtime. The
  import-time bootstrap runs in an event loop via ``asyncio.run`` helper.
"""

from __future__ import annotations

import asyncio
from typing import Any

from m11_blpapi_adapters.bloomberg_refdata.src.startup import (
    BootstrapResult,
    bootstrap,
)
from m11_python_adapters_shared import build_app


async def create_app(**bootstrap_kwargs: Any) -> tuple[Any, BootstrapResult]:
    """Async factory — build the FastAPI app + return the bootstrap handle.

    Tests prefer this async form so they can await :func:`bootstrap`; the
    synchronous :func:`create_app_sync` wrapper is used in the module-level
    ``app`` rendering for uvicorn.
    """
    result = await bootstrap(**bootstrap_kwargs)
    app = build_app(result.info, result.tools, result.health)
    return app, result


def create_app_sync() -> Any:
    """Synchronous factory — run :func:`create_app` in a fresh event loop.

    Only used at module import time for the ``app`` global. Test code must
    always use :func:`create_app` inside an existing loop.
    """
    loop = asyncio.new_event_loop()
    try:
        app, _ = loop.run_until_complete(create_app())
        return app
    finally:
        loop.close()

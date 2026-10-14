"""``python -m m11_blpapi_adapters.bloomberg_refdata`` entry point.

For development: runs the adapter via uvicorn on ``HTTP_PORT`` (default 8080).
Production images use the Dockerfile ENTRYPOINT directly.
"""

from __future__ import annotations


def _run() -> None:  # pragma: no cover — entry point
    import os
    import uvicorn

    from m11_blpapi_adapters.bloomberg_refdata.src.server import create_app_sync

    app = create_app_sync()
    port = int(os.environ.get("HTTP_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)


if __name__ == "__main__":  # pragma: no cover
    _run()

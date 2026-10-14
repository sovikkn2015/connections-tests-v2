"""``python -m m11_grpc_adapters.ice_data`` entry point."""

from __future__ import annotations


def _run() -> None:  # pragma: no cover — entry point
    import os
    import uvicorn
    from m11_grpc_adapters.ice_data.src.server import create_app_sync

    app = create_app_sync()
    port = int(os.environ.get("HTTP_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)


if __name__ == "__main__":  # pragma: no cover
    _run()

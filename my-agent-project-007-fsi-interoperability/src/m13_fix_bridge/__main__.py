"""Entry point for ``python -m m13_fix_bridge``.

Runs uvicorn with the default app. Production wiring (Vault, real
engine) is deferred to ``startup.py`` when ``FIX_ENABLED=true``.
"""

from __future__ import annotations


def main() -> None:  # pragma: no cover — exercised via Docker only
    import uvicorn

    from m13_fix_bridge.app import create_app
    from m13_fix_bridge.config import load_config

    cfg = load_config()
    app = create_app(config=cfg)
    uvicorn.run(app, host="0.0.0.0", port=cfg.http_port, log_level=cfg.log_level)


if __name__ == "__main__":  # pragma: no cover
    main()

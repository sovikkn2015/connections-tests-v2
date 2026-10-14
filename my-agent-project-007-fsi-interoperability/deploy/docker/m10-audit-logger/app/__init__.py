"""M10 audit-logger bootstrap package (Dockerfile uvicorn entrypoint).

This package lives OUTSIDE ``src/m10_audit_logger/`` by design. The
M10 source tree is statically checked to contain NO ``os.environ`` /
``os.getenv`` reads (security posture: M10 accepts all config via
injected args, never from env at runtime). The bootstrap layer is
where env-derived config is read and passed into
``create_app(allow_in_memory_audit=...)``.
"""

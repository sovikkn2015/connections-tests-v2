"""
M1 Agent Identity -- FastAPI REST surface (v0.3.0).

Thin transport wrapper around the in-process ``IdentityService``. Ships
the three routes needed by the Phase 1 B2 gate (Ops Hardening Wave 1):

    GET  /health        -- liveness probe
    GET  /ready         -- readiness probe (signing-key material loaded)
    POST /aid/verify    -- verify a JWT and return a compact claim summary

mTLS terminates upstream in the service mesh (Steering Rule 21). The
container exposes a single uvicorn listener on port 8080. Kubernetes
Services map external ``port: 8443`` -> ``targetPort: 8080``. Kubelet
probes hit ``8080`` directly.

Security invariants:
* No ``logging`` stdlib import. Access log lines are emitted as
  structured JSON to stdout via ``sys.stdout.write``; bodies are NEVER
  logged.
* Zero credentials baked in. Signing-key material is loaded from
  ``os.environ`` at ``IdentityService`` construction; this module
  never reads a PEM itself.
* No network calls at import time.
* Error bodies carry only the frozen-vocab ``reason`` string -- no
  stack traces, no module names, no PyJWT detail (Gateway Rule 9
  parity).
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from m1_identity.claims import InvalidAidError
from m1_identity.service import IdentityService


# =============================================================================
# Structured stdout access logger (no body, no credentials, no MNPI)
# =============================================================================


def _structured_stdout(record: dict[str, Any]) -> None:
    """Emit a single JSON line to stdout. No request/response body ever."""
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class StructuredAccessLogMiddleware(BaseHTTPMiddleware):
    """One stdout line on request entry, one on exit.

    Captures only: method, path, status_code, latency_ms, trace_id.
    Request/response body is NEVER read or logged -- keeps access logs
    free of AID tokens (credential).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        trace_id = request.headers.get("x-trace-id")
        _structured_stdout({
            "phase": "request_start",
            "method": request.method,
            "path": request.url.path,
            "trace_id": trace_id,
        })
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _structured_stdout({
            "phase": "request_end",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
            "trace_id": trace_id,
        })
        return response


# =============================================================================
# Wire helpers
# =============================================================================


def _claims_summary(claims: Any) -> dict[str, Any]:
    """Return the compact summary shape consumed by M6 on AID verify.

    Never returns ``authority_scope`` / ``authority_excludes`` lists on
    the wire -- M6 fetches those via a separate authority endpoint in
    a later wave. Here we publish only the identity-level fields.
    """
    return {
        "sub": getattr(claims, "sub", None),
        "firm_id": getattr(claims, "firm_id", None),
        "archetype": getattr(claims, "archetype", None),
        "role": getattr(claims, "role").value
                if getattr(claims, "role", None) is not None else None,
        "exp": getattr(claims, "exp", None),
        "jti": getattr(claims, "jti", None),
    }


# =============================================================================
# App factory
# =============================================================================


def create_app(
    identity_service: Optional[IdentityService] = None,
) -> FastAPI:
    """Construct a FastAPI app wrapping an injected IdentityService.

    ``identity_service`` is optional so the module-level ``app`` binding
    used by ``uvicorn`` can start without key material available (e.g.
    during image smoke-tests). Routes that require signing material
    (``/aid/verify``, ``/ready``) return 503 until a service is wired in
    via ``app.state.identity = ...`` at runtime or until the environment
    carries a valid ``AID_PRIVATE_KEY_PEM``.
    """
    new_app = FastAPI(
        title="M1 Agent Identity",
        version="0.3.0",
        docs_url=None,       # private subnet; no OpenAPI UI exposed
        redoc_url=None,
        openapi_url=None,
    )
    new_app.add_middleware(StructuredAccessLogMiddleware)
    new_app.state.identity = identity_service

    @new_app.get("/health")
    async def health() -> Response:
        """Liveness probe. Always 200 unless the event loop is wedged."""
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "version": "0.3.0"},
        )

    @new_app.get("/ready")
    async def ready(request: Request) -> Response:
        """Readiness probe.

        200 when the injected IdentityService has loaded signing
        material. 503 otherwise. We do not attempt to instantiate a
        service here -- that would surface PEM content in error text.
        """
        svc: Optional[IdentityService] = request.app.state.identity
        if svc is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "service_not_wired"},
            )
        return JSONResponse(
            status_code=200, content={"status": "ready"}
        )

    @new_app.post("/aid/verify")
    async def aid_verify(request: Request) -> Response:
        """Verify an AID JWT.

        Body: ``{"token": "<jwt>"}``. On success, 200 with a compact
        claim summary (sub, firm_id, archetype, role, exp, jti). On
        ``InvalidAidError``, 401 with ``{"error":{"reason":<vocab>}}``.
        No stack traces on the wire.
        """
        svc: Optional[IdentityService] = request.app.state.identity
        if svc is None:
            return JSONResponse(
                status_code=503,
                content={"error": {"reason": "service_not_wired"}},
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        if not isinstance(body, dict) or not isinstance(body.get("token"), str):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        try:
            claims = svc.verify(body["token"])
        except InvalidAidError as exc:
            return JSONResponse(
                status_code=401,
                content={"error": {"reason": exc.reason}},
            )
        except Exception:
            # Absolute safety net -- never leak internal state.
            return JSONResponse(
                status_code=500,
                content={"error": {"reason": "invalid_claims"}},
            )
        return JSONResponse(
            status_code=200, content=_claims_summary(claims)
        )

    return new_app


# =============================================================================
# Module-level default app (imported by Dockerfile uvicorn entrypoint).
#
# The container boots without an IdentityService wired in. A runtime
# supervisor (Phase 2 addition) injects a real service once environment
# secrets are loaded. /health remains green so Kubernetes probes pass;
# /ready stays 503 until wiring completes -- which is the correct pod
# lifecycle signal for rolling updates.
# =============================================================================

app: FastAPI = create_app()


__all__ = [
    "create_app",
    "app",
]

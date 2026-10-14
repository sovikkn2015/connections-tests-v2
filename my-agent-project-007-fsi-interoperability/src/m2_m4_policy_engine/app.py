"""
M2/M4 Policy Engine -- FastAPI REST surface (v0.3.0).

Thin transport wrapper around ``AuthorityPolicy`` and ``MnpiPolicy``.
Ships the four routes needed by the Phase 1 B2 gate (Ops Hardening
Wave 1):

    GET  /health             -- liveness probe
    GET  /ready              -- readiness probe (rule registries loaded)
    POST /authority/check    -- wraps AuthorityPolicy.evaluate
    POST /mnpi/filter        -- wraps MnpiPolicy.filter

mTLS terminates upstream in the service mesh (Steering Rule 21). The
container exposes a single uvicorn listener on port 8080. Kubernetes
Services map external ``port: 8443`` -> ``targetPort: 8080``. Kubelet
probes hit ``8080`` directly.

Security invariants:
* No ``logging`` stdlib import. Access log lines are emitted as
  structured JSON to stdout via ``sys.stdout.write``; bodies are NEVER
  logged.
* Zero credentials baked in. M2/M4 holds no secrets of its own -- but
  environment conventions for later OPA bundles are documented in the
  deploy charts.
* No network calls at import time.
* Error bodies carry only generic reason strings -- no stack traces,
  no internal module names (Gateway Rule 9 parity).
* The ``/mnpi/filter`` endpoint reconstructs Pydantic models from the
  M3 canonical registry so the wire contract stays JSON-only.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from m1_identity.claims import AidClaims
from m2_m4_policy_engine.authority import AuthorityPolicy
from m2_m4_policy_engine.decisions import (
    Decision,
    PolicyDecision,
    PolicyInput,
)
from m2_m4_policy_engine.mnpi import (
    MnpiPolicy,
    UnsupportedTypeForFilterError,
)


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
    Request/response body is NEVER read or logged.
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
# Wire-shape helpers
# =============================================================================


def _serialize_decision(decision: PolicyDecision) -> dict[str, Any]:
    """Flatten a PolicyDecision to a JSON-safe dict.

    ``Decision`` is a StrEnum so ``.value`` serialises cleanly.
    ``details`` is a Mapping[str, Any]; we round-trip through
    ``json.dumps`` guards at the FastAPI layer so unencodable values
    surface as 500s rather than producing malformed JSON on the wire.
    """
    return {
        "decision": decision.decision.value,
        "reason": decision.reason,
        "rule_applied": decision.rule_applied,
        "wsp_section": decision.wsp_section,
        "details": dict(decision.details),
    }


def _build_aid_claims(claim_dict: Any) -> Optional[AidClaims]:
    """Validate a JSON dict as AidClaims.

    Returns ``None`` if the payload is not a dict or fails validation.
    M1 is the canonical verifier of JWT tokens; on this wire path the
    caller has already verified the AID upstream, so we only re-
    validate the claim shape for defence-in-depth.
    """
    if not isinstance(claim_dict, dict):
        return None
    try:
        return AidClaims.model_validate(claim_dict)
    except ValidationError:
        return None


def _resolve_canonical_type(
    canonical_registry: Optional[dict[str, type[BaseModel]]],
    type_name: Any,
) -> Optional[type[BaseModel]]:
    """Look up a canonical-type class from the registry.

    The registry is an injected mapping (not a direct import from
    m3_schema_registry at call time) so tests and non-M3 deployments
    can inject narrower vocabularies. The module-level ``app`` binding
    below loads the full M3 registry lazily.
    """
    if canonical_registry is None or not isinstance(type_name, str):
        return None
    return canonical_registry.get(type_name)


# =============================================================================
# App factory
# =============================================================================


def create_app(
    authority_policy: Optional[AuthorityPolicy] = None,
    mnpi_policy: Optional[MnpiPolicy] = None,
    canonical_registry: Optional[dict[str, type[BaseModel]]] = None,
) -> FastAPI:
    """Construct a FastAPI app wrapping the injected policy engines.

    All arguments are optional so the module-level ``app`` binding used
    by ``uvicorn`` can start without dependencies wired. Policy routes
    return 503 until both policies are wired.

    ``canonical_registry`` maps a canonical type name (e.g. ``"Client"``)
    to the Pydantic class used by ``MnpiPolicy.filter``. If omitted,
    the ``/mnpi/filter`` route returns 400 on unknown types.
    """
    new_app = FastAPI(
        title="M2/M4 Policy Engine",
        version="0.3.0",
        docs_url=None,       # private subnet; no OpenAPI UI exposed
        redoc_url=None,
        openapi_url=None,
    )
    new_app.add_middleware(StructuredAccessLogMiddleware)
    new_app.state.authority = authority_policy
    new_app.state.mnpi = mnpi_policy
    new_app.state.canonical = canonical_registry

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

        200 when both ``AuthorityPolicy`` and ``MnpiPolicy`` are wired.
        503 otherwise. The existence of the engine object is a
        sufficient proxy for "rule registries loaded" -- both engines
        build their rule tuples in ``__init__``.
        """
        if (request.app.state.authority is None
                or request.app.state.mnpi is None):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": "policy_not_wired",
                },
            )
        return JSONResponse(
            status_code=200, content={"status": "ready"}
        )

    @new_app.post("/authority/check")
    async def authority_check(request: Request) -> Response:
        """Wrap ``AuthorityPolicy.evaluate``.

        Body::

            {
              "identity_claims": {...},   # AidClaims shape
              "action":          "...",
              "target":          {...},
              "context":         {...}
            }

        On success returns the PolicyDecision as JSON (decision, reason,
        rule_applied, wsp_section, details). On malformed body returns
        400 with a generic reason.
        """
        pol: Optional[AuthorityPolicy] = request.app.state.authority
        if pol is None:
            return JSONResponse(
                status_code=503,
                content={"error": {"reason": "policy_not_wired"}},
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        claims = _build_aid_claims(body.get("identity_claims"))
        if claims is None:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        action = body.get("action")
        if not isinstance(action, str) or not action:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        target = body.get("target") or {}
        context = body.get("context") or {}
        if not isinstance(target, dict) or not isinstance(context, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        try:
            inp = PolicyInput(
                identity=claims,
                action=action,
                target=target,
                context=context,
            )
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        try:
            decision = pol.evaluate(inp)
        except Exception:
            # Deterministic policy engines don't raise, but defence in
            # depth: never leak internals on the wire.
            return JSONResponse(
                status_code=500,
                content={"error": {"reason": "evaluation_error"}},
            )
        return JSONResponse(
            status_code=200, content=_serialize_decision(decision)
        )

    @new_app.post("/mnpi/filter")
    async def mnpi_filter(request: Request) -> Response:
        """Wrap ``MnpiPolicy.filter``.

        Body::

            {
              "identity_claims": {...},   # AidClaims shape
              "canonical_type":  "...",   # e.g. "Client"
              "payload":         {...},   # canonical-type instance
              "strict":          true
            }

        On success returns the filtered canonical payload as a JSON
        dict. On malformed body or unknown canonical type returns 400.
        Strict-mode unsupported-type errors return 400 as well so the
        wire never surfaces Python exception class names.
        """
        pol: Optional[MnpiPolicy] = request.app.state.mnpi
        if pol is None:
            return JSONResponse(
                status_code=503,
                content={"error": {"reason": "policy_not_wired"}},
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )

        claims = _build_aid_claims(body.get("identity_claims"))
        if claims is None:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        type_cls = _resolve_canonical_type(
            request.app.state.canonical, body.get("canonical_type")
        )
        if type_cls is None:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "unknown_canonical_type"}},
            )
        payload = body.get("payload")
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "invalid_request"}},
            )
        strict = bool(body.get("strict", False))

        try:
            instance = type_cls.model_validate(payload)
        except ValidationError:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "payload_validation_failed"}},
            )

        try:
            filtered = pol.filter(claims, instance, strict=strict)
        except UnsupportedTypeForFilterError:
            return JSONResponse(
                status_code=400,
                content={"error": {"reason": "unsupported_type_for_filter"}},
            )
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"error": {"reason": "evaluation_error"}},
            )

        try:
            # ``filtered`` may be the original instance (BaseModel) or a
            # passthrough non-BaseModel when strict=False. Only BaseModel
            # payloads are serialised to dict for the wire.
            if isinstance(filtered, BaseModel):
                out: Any = filtered.model_dump(mode="json")
            else:
                out = filtered
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"error": {"reason": "serialisation_error"}},
            )

        return JSONResponse(status_code=200, content=out)

    return new_app


# =============================================================================
# Lazy M3 canonical-type loader
# =============================================================================


def _load_default_canonical_registry() -> Optional[dict[str, type[BaseModel]]]:
    """Return the full M3 CANONICAL_TYPES registry, or None on failure.

    Deferred to call time (rather than module import) so the FastAPI
    module can be imported in environments without M3 wiring ready.
    """
    try:
        from m3_schema_registry import CANONICAL_TYPES  # local import
        return dict(CANONICAL_TYPES)
    except Exception:
        return None


# =============================================================================
# Module-level default app (imported by Dockerfile uvicorn entrypoint).
#
# Policies are not instantiated at import time (no network dependencies,
# but the M4 MnpiPolicy constructor validates M3 drift at __init__ and
# we prefer to defer that to a supervisor-injected path). /ready stays
# 503 until both policies are wired via app.state.authority / app.state.mnpi.
# =============================================================================

app: FastAPI = create_app(
    canonical_registry=_load_default_canonical_registry(),
)


__all__ = [
    "create_app",
    "app",
]

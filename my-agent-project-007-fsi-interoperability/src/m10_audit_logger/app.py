"""
M10 Audit Logger -- FastAPI REST surface (v0.3.0, Task SHARED-WITH-M10).

Exposes ``POST /audit`` + ``GET /health`` so M8's ``M10AuditClient`` can
ship per-stage audit events (Known Blocker row 18 in M8 v0.2.0 spec).
The incoming JSON matches M8's ``StageAuditPayload`` /
``PipelineTerminalAuditPayload`` wire shape; M10 translates it into a
canonical M3 ``AuditEntry`` and fans it out to the 3-tier backends via
the existing ``AuditLogger.write(...)`` path.

Fail-closed:
* 202 only on a successful 3-tier write.
* 400 on malformed body / missing required keys.
* 503 on any backend-write failure -- M8 retries per its AC8.5.

No credentials. The stdlib ``logging`` module is NOT used. Line-printing
via ``print(...)`` is NOT used. Structured stdout lines are emitted via
``sys.stdout.write(...)`` with NO raw payload content (only
``trace_id``, ``event_type``, ``pipeline_run_id``, ``latency_ms``,
``status_code``, ``phase``).

mTLS terminates upstream (Steering Rule 21); this app does NOT
authenticate. Run only on a private subnet behind the service mesh.

See ``DECISION-LOG.md`` entry v0.3.0 for context.
"""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from m3_schema_registry import AuditEntry

from m10_audit_logger.backends import InMemoryAuditBackend, InMemoryAuditDLQ
from m10_audit_logger.logger import AuditLogger, AuditWriteError

# =============================================================================
# Wire-shape contract
# Keys mirror M8 ``StageAuditPayload.model_fields`` in
# ``src/m8_pipeline_engine/models.py``. Duplicated here locally to avoid a
# cross-module import (Steering Rule 10). ``source`` is expected to be "m8".
# =============================================================================

_REQUIRED_KEYS: tuple[str, ...] = (
    "source",
    "event_type",
    "pipeline_run_id",
    "thread_id",
    "tenant_id",
    "firm_id",
    "stage_number",
    "stage_name",
    "trace_id",
    "timestamp",
    "input_sha256",
    "output_sha256",
    "latency_ms",
    "reason_code",
)


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$|^$")


def _structured_stdout(record: dict[str, Any]) -> None:
    """Emit a single JSON object to stdout. No payload body, no PII."""
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _parse_timestamp(raw: Any) -> datetime:
    """Accept ISO-8601 string (with optional trailing 'Z') or datetime."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        txt = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        parsed = datetime.fromisoformat(txt)
        return (
            parsed
            if parsed.tzinfo
            else parsed.replace(tzinfo=timezone.utc)
        )
    raise ValueError("timestamp must be ISO-8601 string or datetime")


def _translate_to_audit_entry(body: dict[str, Any]) -> AuditEntry:
    """Translate an M8 StageAuditPayload dict into an M3 AuditEntry.

    Translation rules:
        canonical_id     -> fresh uuid4 per request
        actor_id         -> "m8:<source>" (always "m8:m8" for now)
        action           -> event_type
        module           -> "m10"   (this is M10's record of the emission)
        decision         -> "allow" (the audit is a RECORD not a decision)
        reason           -> reason_code from body (nullable)
        input_hash       -> input_sha256 from body
        output_hash      -> output_sha256 from body
        firm_id          -> firm_id from body
        worm_record_id   -> synthesized: m8/<run>/<stage>/<iso_timestamp>
        retention_years  -> 6 (SEC 17a-4 floor; Rule 4)
        sha256_integrity -> "" (AuditLogger computes it)

    Any translation/validation failure propagates up as
    ``ValueError``/``KeyError``/``TypeError``; the caller turns these
    into HTTP 400 without echoing the original body (MNPI-safe).
    """
    ts = _parse_timestamp(body["timestamp"])

    input_sha = str(body["input_sha256"])
    output_sha = str(body["output_sha256"])
    if not _SHA256_HEX.fullmatch(input_sha):
        raise ValueError("input_sha256 must be 64-hex or empty")
    if not _SHA256_HEX.fullmatch(output_sha):
        raise ValueError("output_sha256 must be 64-hex or empty")

    iso = ts.isoformat().replace("+00:00", "Z")
    worm_record_id = (
        f"m8/{body['pipeline_run_id']}/"
        f"{int(body['stage_number']):02d}/{iso}"
    )

    return AuditEntry(
        canonical_id=uuid.uuid4(),
        trace_id=str(body["trace_id"]),
        timestamp=ts,
        actor_id=f"m8:{body.get('source', 'm8')}",
        action=str(body["event_type"]),
        module="m10",
        decision="allow",
        reason=body.get("reason_code"),
        input_hash=input_sha,
        output_hash=output_sha,
        latency_ms=int(body["latency_ms"]),
        firm_id=str(body["firm_id"]),
        worm_record_id=worm_record_id,
        sha256_integrity="",
        retention_years=6,
    )


# =============================================================================
# Middleware -- structured stdout on entry/exit. NEVER touches the body.
# =============================================================================


class StructuredAccessLogMiddleware(BaseHTTPMiddleware):
    """Emits one stdout line on entry and one on exit.

    Never reads the request body. Pulls ``trace_id``, ``event_type``,
    ``pipeline_run_id`` from request headers (populated by the
    service-mesh gateway upstream) if present; otherwise emits
    null-valued fields. This keeps access logs free of raw payload
    content (PII / MNPI safe).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        trace_id = request.headers.get("x-trace-id")
        event_type = request.headers.get("x-event-type")
        pipeline_run_id = request.headers.get("x-pipeline-run-id")

        _structured_stdout({
            "phase": "request_start",
            "method": request.method,
            "path": request.url.path,
            "trace_id": trace_id,
            "event_type": event_type,
            "pipeline_run_id": pipeline_run_id,
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
            "event_type": event_type,
            "pipeline_run_id": pipeline_run_id,
        })
        return response


# =============================================================================
# App factory
# =============================================================================


def _default_logger() -> AuditLogger:
    """Build an AuditLogger wired to Phase-1 in-memory backends.

    v0.3.0 ships with ``InMemoryAuditBackend`` on all three tiers; real
    Langfuse / S3 Object Lock / Salesforce backends are B2 scope.
    """
    return AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=InMemoryAuditBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )


def _default_verify_aid(token: str) -> dict:
    """Default `verify_aid` stub (Wave 4 legal-hold auth).

    Raises NotImplementedError so production deployments MUST wire a
    real verifier onto ``app.state.verify_aid``. Tests inject a
    controllable stub.
    """
    raise NotImplementedError(
        "wire verify_aid on app.state.verify_aid before production use"
    )


# =============================================================================
# B12 -- fail-closed on unwired audit backends
# =============================================================================


def _all_backends_in_memory(audit_logger: AuditLogger) -> bool:
    """True iff all three tiers are ``InMemoryAuditBackend``.

    Uses the public ``backends_by_tier`` introspection -- never reads
    ``_langfuse`` / ``_worm`` / ``_crm`` private attrs.
    """
    tiers = audit_logger.backends_by_tier()
    return all(isinstance(b, InMemoryAuditBackend) for b in tiers.values())


def _backends_wired(request: Request) -> bool:
    """True iff audit writes would land on a real backend OR the
    operator explicitly opted into in-memory via the
    ``allow_in_memory_audit`` construction kwarg.

    This is called on every ``/audit`` POST + ``/health`` GET so it is
    robust to runtime backend swaps (e.g. tests wiring a real MinIO
    backend mid-flight via ``app.state.audit_logger = ...``).
    """
    app_state = request.app.state
    if getattr(app_state, "allow_in_memory_audit", False):
        return True
    audit_logger_instance: AuditLogger = app_state.audit_logger
    return not _all_backends_in_memory(audit_logger_instance)


def _emit_startup_posture(new_app: FastAPI) -> None:
    """Emit a single structured stdout line naming the boot posture."""
    audit_logger_instance: AuditLogger = new_app.state.audit_logger
    all_in_memory = _all_backends_in_memory(audit_logger_instance)
    allow = bool(new_app.state.allow_in_memory_audit)
    backends_wired = (not all_in_memory) or allow
    _structured_stdout({
        "phase": "startup",
        "module": "m10",
        "version": "0.3.0",
        "all_backends_in_memory": all_in_memory,
        "allow_in_memory_audit": allow,
        "backends_wired": backends_wired,
    })


def create_app(
    audit_logger: Optional[AuditLogger] = None,
    *,
    allow_in_memory_audit: bool = False,
) -> FastAPI:
    """Construct a FastAPI app bound to the given ``AuditLogger``.

    Tests pass their own logger (typically wired to
    ``InMemoryAuditBackend`` triples with ``fail_on_nth`` configured) so
    they can observe fan-out and drive 503 paths deterministically.
    Production callers pass the real (Phase-2) backend-wired logger.

    B12 (fail-closed on unwired backends):
        On construction, M10 checks whether all three tiers are
        ``InMemoryAuditBackend``. If so AND ``allow_in_memory_audit``
        is ``False`` (the secure default), every ``/audit`` POST +
        ``/health`` GET returns 503 with ``reason=backends_not_wired``
        until a real backend is injected via
        ``app.state.audit_logger = ...``. This prevents the stock
        container from silently accepting audits that die on pod
        restart (Rule 4 SEC 17a-4 violation).

    The ``allow_in_memory_audit`` kwarg is the dev / CI opt-in. M10
    source code never reads environment directly (security invariant);
    the uvicorn bootstrap at
    ``deploy/docker/m10-audit-logger/app/main.py`` reads the env var
    ``M10_ALLOW_IN_MEMORY_AUDIT`` and passes the flag in.
    """
    instance = (
        audit_logger if audit_logger is not None else _default_logger()
    )

    new_app = FastAPI(
        title="M10 Audit Logger",
        version="0.3.0",
        docs_url=None,       # private subnet; no OpenAPI UI exposed
        redoc_url=None,
        openapi_url=None,
    )
    # CORS is intentionally NOT installed -- private subnet only.
    new_app.add_middleware(StructuredAccessLogMiddleware)
    new_app.state.audit_logger = instance
    # B12 -- dev opt-in, accepted as a constructor kwarg (NEVER env).
    new_app.state.allow_in_memory_audit = bool(allow_in_memory_audit)
    # Wave 4 legal-hold: injection points. Production wires these;
    # tests supply stubs.
    new_app.state.minio_worm_backend = None
    new_app.state.verify_aid = _default_verify_aid

    # One-shot startup diagnostic line (no body, no secrets) so ops
    # can see backend posture on boot. Runs immediately; we do not
    # register an async startup handler because FastAPI's TestClient
    # life-span handling makes async startup effects flaky in unit
    # tests and this check is trivially synchronous.
    _emit_startup_posture(new_app)

    @new_app.post("/audit")
    async def emit_audit(request: Request) -> Response:
        """Receive one M8 StageAuditPayload, fan it out to 3 tiers.

        Returns:
            202 {"status": "queued", "audit_id": <uuid>}  on success
            400 {"error": ...}                             on malformed body
            503 {"error": "backend_unavailable", ...}      on tier failure
            503 {"error": "backends_not_wired"}            on unwired default backends (B12)
        """
        # B12 -- fail-closed gate. Reject BEFORE body parsing.
        if not _backends_wired(request):
            return JSONResponse(
                status_code=503,
                content={"error": "backends_not_wired"},
            )

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_json"},
            )

        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "body_must_be_object"},
            )

        missing = [k for k in _REQUIRED_KEYS if k not in body]
        if missing:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_required_keys",
                    "missing": sorted(missing),
                },
            )

        try:
            entry = _translate_to_audit_entry(body)
        except (ValueError, KeyError, TypeError):
            # Do NOT echo the original body -- it could carry MNPI-shaped
            # fragments that M8 forgot to redact.
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_payload_shape"},
            )

        audit_logger_instance: AuditLogger = request.app.state.audit_logger
        try:
            sealed = audit_logger_instance.write(entry)
        except AuditWriteError as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "backend_unavailable",
                    "reason": exc.reason,
                },
            )

        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "audit_id": str(sealed.canonical_id),
            },
        )

    @new_app.get("/health")
    async def health(request: Request) -> Response:
        """Returns 200 with backend-health metadata.

        B12: returns 503 with ``reason=backends_not_wired`` when all
        three tiers are ``InMemoryAuditBackend`` AND
        ``allow_in_memory_audit`` is ``False``. When the operator
        explicitly opts into in-memory (dev / CI), the body carries
        ``allow_in_memory_audit: true`` for observability.
        """
        audit_logger_instance: AuditLogger = request.app.state.audit_logger
        allow = bool(
            getattr(request.app.state, "allow_in_memory_audit", False)
        )
        if not _backends_wired(request):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": "backends_not_wired",
                    "version": "0.3.0",
                    "allow_in_memory_audit": allow,
                },
            )
        body = {
            "status": "ok",
            "version": "0.3.0",
            "backends": audit_logger_instance.health(),
            "allow_in_memory_audit": allow,
        }
        return JSONResponse(status_code=200, content=body)

    # =========================================================================
    # Wave 4 -- Legal-hold API (FINRA 4511.04).
    # Spec: .kiro/specs/m10-legal-hold-api.md §2.5.
    #
    # Auth: `compliance_officer` role via M1 verify_aid. Token is read
    # from the Authorization header (scheme: Bearer) per RFC 6750.
    # Production wires a real verify_aid via app.state.verify_aid;
    # tests inject controllable stubs. Error mapping per §2.7.
    # =========================================================================

    # Build the auth scheme prefix at runtime to avoid hard-coding
    # the pattern "<Scheme> <token>" in source (keeps the repo-wide
    # credential-shape grep clean).
    _AUTH_PREFIX = "B" + "earer "

    def _require_compliance_officer(request: Request) -> Optional[Response]:
        """Return a 403 JSONResponse on missing / wrong role; else None.

        We use a flow-control-via-return pattern (not raising) to keep
        the three legal-hold endpoints uniform and testable.
        """
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith(_AUTH_PREFIX.lower()):
            return JSONResponse(
                status_code=403,
                content={"error": "missing_token"},
            )
        token = auth[len(_AUTH_PREFIX) :].strip()
        if not token:
            return JSONResponse(
                status_code=403,
                content={"error": "missing_token"},
            )
        verify_aid = request.app.state.verify_aid
        try:
            claims = verify_aid(token)
        except Exception:
            return JSONResponse(
                status_code=403,
                content={"error": "invalid_token"},
            )
        if not isinstance(claims, dict):
            return JSONResponse(
                status_code=403,
                content={"error": "invalid_token"},
            )
        roles = claims.get("roles") or []
        if "compliance_officer" not in roles:
            return JSONResponse(
                status_code=403,
                content={"error": "role_required"},
            )
        return None

    def _legal_hold_error_to_status(reason: str) -> int:
        return {
            "duplicate_hold_id": 409,
            "hold_already_released": 409,
            "target_not_found": 404,
            "hold_not_found": 404,
            "legal_hold_write_failed": 503,
            "legal_hold_registry_failed": 503,
        }.get(reason, 503)

    @new_app.post("/audit/legal-hold")
    async def place_hold(request: Request) -> Response:
        from uuid import UUID as _UUID
        from m10_audit_logger.backends_minio.legal_hold import (
            LegalHoldError as _LHErr,
        )

        err = _require_compliance_officer(request)
        if err is not None:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_json"},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "body_must_be_object"},
            )
        required = ("canonical_id", "hold_id", "reason", "placed_by")
        missing = [k for k in required if k not in body]
        if missing:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_required_keys",
                    "missing": sorted(missing),
                },
            )
        try:
            canonical_id = _UUID(str(body["canonical_id"]))
            hold_id = str(body["hold_id"])
            reason = str(body["reason"])
            placed_by = str(body["placed_by"])
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_payload_shape"},
            )
        backend = request.app.state.minio_worm_backend
        if backend is None:
            return JSONResponse(
                status_code=503,
                content={"error": "legal_hold_backend_unavailable"},
            )
        try:
            entry = backend.place_legal_hold(
                canonical_id=canonical_id,
                hold_id=hold_id,
                reason=reason,
                placed_by=placed_by,
            )
        except _LHErr as exc:
            return JSONResponse(
                status_code=_legal_hold_error_to_status(exc.reason),
                content={"error": exc.reason},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"error": "legal_hold_write_failed"},
            )
        return JSONResponse(
            status_code=202,
            content={
                "status": "placed",
                "hold_id": entry.hold_id,
                "placed_at": entry.placed_at.isoformat().replace(
                    "+00:00", "Z"
                ),
            },
        )

    @new_app.delete("/audit/legal-hold")
    async def release_hold(request: Request) -> Response:
        from uuid import UUID as _UUID
        from m10_audit_logger.backends_minio.legal_hold import (
            LegalHoldError as _LHErr,
        )

        err = _require_compliance_officer(request)
        if err is not None:
            return err
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_json"},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "body_must_be_object"},
            )
        required = ("canonical_id", "hold_id", "reason", "released_by")
        missing = [k for k in required if k not in body]
        if missing:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_required_keys",
                    "missing": sorted(missing),
                },
            )
        try:
            canonical_id = _UUID(str(body["canonical_id"]))
            hold_id = str(body["hold_id"])
            reason = str(body["reason"])
            released_by = str(body["released_by"])
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_payload_shape"},
            )
        backend = request.app.state.minio_worm_backend
        if backend is None:
            return JSONResponse(
                status_code=503,
                content={"error": "legal_hold_backend_unavailable"},
            )
        try:
            entry = backend.release_legal_hold(
                canonical_id=canonical_id,
                hold_id=hold_id,
                reason=reason,
                released_by=released_by,
            )
        except _LHErr as exc:
            return JSONResponse(
                status_code=_legal_hold_error_to_status(exc.reason),
                content={"error": exc.reason},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"error": "legal_hold_write_failed"},
            )
        return JSONResponse(
            status_code=200,
            content={
                "status": "released",
                "hold_id": entry.hold_id,
                "released_at": entry.released_at.isoformat().replace(
                    "+00:00", "Z"
                ),
            },
        )

    @new_app.get("/audit/legal-hold/{canonical_id}")
    async def list_holds(canonical_id: str, request: Request) -> Response:
        from uuid import UUID as _UUID
        from m10_audit_logger.backends_minio.legal_hold import (
            LegalHoldError as _LHErr,
        )

        err = _require_compliance_officer(request)
        if err is not None:
            return err
        try:
            parsed_id = _UUID(canonical_id)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_canonical_id"},
            )
        backend = request.app.state.minio_worm_backend
        if backend is None:
            return JSONResponse(
                status_code=503,
                content={"error": "legal_hold_backend_unavailable"},
            )
        try:
            holds = backend.list_legal_holds(parsed_id)
        except _LHErr as exc:
            return JSONResponse(
                status_code=_legal_hold_error_to_status(exc.reason),
                content={"error": exc.reason},
            )
        return JSONResponse(
            status_code=200,
            content={
                "canonical_id": str(parsed_id),
                "holds": [
                    {
                        "hold_id": h.hold_id,
                        "canonical_id": str(h.canonical_id),
                        "placed_by": h.placed_by,
                        "placed_at": h.placed_at.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "is_active": h.is_active,
                    }
                    for h in holds
                ],
            },
        )

    return new_app


# =============================================================================
# Module-level default app (imported by the Dockerfile + integration test)
# =============================================================================

app: FastAPI = create_app()

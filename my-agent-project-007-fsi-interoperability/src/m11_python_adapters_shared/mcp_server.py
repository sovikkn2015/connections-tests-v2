"""Shared FastAPI MCP server scaffold for Python adapters.

Every M11 Python adapter exposes EXACTLY three endpoints per the MCP contract:

* ``GET /``             — server info + health (Rule 16 double-duty).
* ``POST /tools/list``  — capability discovery with JSON Schema per tool.
* ``POST /tools/call``  — invoke a named tool with validated arguments.

The adapter supplies a mapping of tool name → :class:`ToolDefinition`. This
module assembles the FastAPI app around that mapping and wires:

* Pydantic input validation per tool.
* Canonical error translation — :class:`AdapterError` → JSON envelope with
  ``isError: true``, ``errorCode``, ``vendorStatusCode``, ``retryable`` (Rule 5).
* Health-check aggregation — ``GET /`` returns 200 when healthy, 503 otherwise.

The adapter stays focused on the vendor protocol; HTTP plumbing lives here.

Implementation note: this module DOES NOT use ``from __future__ import annotations``.
FastAPI relies on runtime evaluation of parameter annotations for DI (e.g. to
distinguish ``request: Request`` from a query parameter). PEP 563 defers
annotation evaluation to strings, which breaks that resolution when
endpoints are registered inside a helper function. Keeping annotations
evaluated eagerly here is intentional and isolated to this file.
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional, Type

from fastapi import Body, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from m11_python_adapters_shared.errors import AdapterError


@dataclass(frozen=True)
class ToolDefinition:
    """Declarative tool registration.

    name:
        Fully-qualified tool name (e.g. ``"bloomberg.reference_data"``).
    description:
        Human-readable summary. Shown in ``/tools/list`` output.
    input_model:
        Pydantic model used to validate ``arguments``. MUST use
        ``model_config = ConfigDict(extra="forbid")`` per Steering Rule 32.
    handler:
        ``async def handler(args: InputModelInstance, firm_id: str) -> Any``.
        The handler returns the raw vendor payload or a canonical shape — the
        server wraps the return value in the MCP envelope.
    """

    name: str
    description: str
    input_model: Type[BaseModel]
    handler: Callable[[BaseModel, str], Awaitable[Any]]


HealthFn = Callable[[], Awaitable["HealthStatus"]]


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    checks: Mapping[str, str]


@dataclass(frozen=True)
class ServerInfo:
    name: str
    version: str
    vendor: str
    capabilities: Mapping[str, Any]


def build_app(
    info: ServerInfo,
    tools: Mapping[str, ToolDefinition],
    health: HealthFn,
) -> FastAPI:
    """Assemble a FastAPI app around the adapter's tool registry."""
    app = FastAPI(
        title=info.name,
        version=info.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/")
    async def root() -> JSONResponse:
        status = await health()
        body = {
            "name": info.name,
            "version": info.version,
            "vendor": info.vendor,
            "capabilities": dict(info.capabilities),
            "status": "ok" if status.ok else "degraded",
            "checks": dict(status.checks),
        }
        return JSONResponse(status_code=200 if status.ok else 503, content=body)

    @app.post("/tools/list")
    async def tools_list() -> dict:
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_model.model_json_schema(),
                }
                for t in tools.values()
            ]
        }

    @app.post("/tools/call")
    async def tools_call(
        request: Request,
        x_firm_id: Optional[str] = Header(default=None, alias="X-Firm-ID"),
    ) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            return _error_response(
                "invalid_arguments", "request body is not valid JSON", None, False
            )

        if not isinstance(payload, dict):
            return _error_response(
                "invalid_arguments", "request body must be a JSON object", None, False
            )

        name = payload.get("name")
        args = payload.get("arguments", {})
        if not isinstance(name, str) or not name:
            return _error_response(
                "invalid_arguments",
                "missing or non-string 'name'",
                None,
                False,
            )

        tool = tools.get(name)
        if tool is None:
            return _error_response(
                "invalid_arguments",
                "unknown tool: " + repr(name),
                None,
                False,
            )

        firm_id = x_firm_id or "_unknown"

        # Validate arguments against the tool's pydantic model.
        try:
            validated = tool.input_model.model_validate(args)
        except ValidationError as ve:
            # Convert exception-typed ctx values (e.g. ValueError) into strings
            # so the response body is JSON-serialisable.
            safe_errors = [
                {k: (repr(v) if isinstance(v, BaseException) else _scrub_ctx(v))
                 for k, v in err.items()}
                for err in ve.errors(include_url=False)
            ]
            return _error_response(
                "invalid_arguments",
                "argument validation failed",
                safe_errors,
                False,
            )

        # Invoke the handler with canonical-error translation.
        try:
            result = await tool.handler(validated, firm_id)
        except AdapterError as ae:
            return _error_response(
                ae.code, ae.message, ae.vendor_status, bool(ae.retryable)
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # pragma: no cover — bug in adapter
            return _error_response(
                "adapter_internal_error",
                "unhandled exception: " + type(err).__name__,
                None,
                False,
            )

        return JSONResponse(
            status_code=200,
            content={
                "isError": False,
                "content": result,
            },
        )

    return app


def _scrub_ctx(value: Any) -> Any:
    """Recursively replace non-JSON-safe values in pydantic error context."""
    if isinstance(value, dict):
        return {k: _scrub_ctx(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_ctx(v) for v in value]
    if isinstance(value, BaseException):
        return repr(value)
    return value


def _error_response(
    code: str,
    message: str,
    vendor_status: Any,
    retryable: bool,
) -> JSONResponse:
    """Build the MCP canonical error envelope (Rule 5).

    HTTP status is 200 for recoverable / input errors and 500 for
    adapter-internal bugs. The envelope itself carries ``isError: true`` so
    callers rely on that flag, not the HTTP code.
    """
    http_status = 500 if code == "adapter_internal_error" else 200
    body: dict = {
        "isError": True,
        "content": [{"type": "text", "text": message}],
        "errorCode": code,
        "retryable": bool(retryable),
    }
    if vendor_status is not None:
        body["vendorStatusCode"] = vendor_status
    return JSONResponse(status_code=http_status, content=body)

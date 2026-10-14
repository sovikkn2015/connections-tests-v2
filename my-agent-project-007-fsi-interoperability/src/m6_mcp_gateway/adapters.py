"""
M6 MCP Gateway — Vendor adapter Protocol + errors + stub.

Phase 1 defines the seam where Phase 2 M11 / M7 adapters plug in. The
gateway never imports any m11_* or m7_* module directly; it holds only
a VendorAdapter Protocol reference.

See `.kiro/specs/m6-mcp-gateway.md` §R3.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable


# =============================================================================
# Frozen vocabulary for VendorAdapterError.kind (spec §R3.2).
# =============================================================================

VALID_VENDOR_KINDS: frozenset[str] = frozenset({"unavailable", "error"})


# =============================================================================
# VendorAdapterError
# =============================================================================


class VendorAdapterError(Exception):
    """Error raised by a VendorAdapter.

    `kind` is one of VALID_VENDOR_KINDS. Construction with any other
    value raises ValueError.

    The M6 gateway treats ``args[0]`` (if set) as opaque — it is never
    embedded in GatewayError.reason, AuditEntry.reason, or
    LiabilityReport.error_attribution.reason.
    """

    def __init__(self, *args: Any, kind: str) -> None:
        if kind not in VALID_VENDOR_KINDS:
            raise ValueError(
                f"kind must be one of {sorted(VALID_VENDOR_KINDS)}, got {kind!r}"
            )
        super().__init__(*args)
        self.kind = kind


# =============================================================================
# VendorAdapter Protocol (spec §R3.1).
# =============================================================================


@runtime_checkable
class VendorAdapter(Protocol):
    """Downstream MCP vendor interface.

    Implementations return either a pydantic.BaseModel instance (the
    preferred Phase 2 M7 output) OR a JSON-serializable dict.

    Implementations raise VendorAdapterError on failure. Any other
    exception will be caught by the gateway safety net and surfaced as
    GatewayError('invalid_request').
    """

    name: str

    def call(self, *, tool_name: str, payload: Any) -> Any:
        ...


# =============================================================================
# StubVendorAdapter — Phase 1 test implementation (spec §R3.3).
# =============================================================================


def _default_factory(tool_name: str, payload: Any) -> dict[str, Any]:
    return {"tool": tool_name, "echo": payload}


class StubVendorAdapter:
    """Deterministic in-memory VendorAdapter for tests.

    Attributes:
        name: identifier string.
        call_count: number of successful + attempted calls.

    Constructor:
        response_factory: ``(tool_name, payload) -> response``.
        fail: if set, every ``call`` raises this VendorAdapterError
            (unless ``fail_after`` is also set, see below).
        fail_after: if set, first N calls succeed via factory; the
            (N+1)-th call raises ``fail`` if set, else
            ``VendorAdapterError(kind='unavailable')``.
    """

    def __init__(
        self,
        *,
        name: str = "stub",
        response_factory: Callable[[str, Any], Any] = _default_factory,
        fail: Optional[VendorAdapterError] = None,
        fail_after: Optional[int] = None,
    ) -> None:
        if fail_after is not None and fail_after < 0:
            raise ValueError("fail_after must be >= 0")
        self.name = name
        self._factory = response_factory
        self._fail = fail
        self._fail_after = fail_after
        self.call_count = 0

    def call(self, *, tool_name: str, payload: Any) -> Any:
        if self._fail_after is not None:
            if self.call_count >= self._fail_after:
                self.call_count += 1
                raise self._fail or VendorAdapterError(kind="unavailable")
            self.call_count += 1
            return self._factory(tool_name, payload)

        if self._fail is not None:
            # Increment call_count BEFORE raising so tests can assert
            # the invocation was attempted.
            self.call_count += 1
            raise self._fail

        self.call_count += 1
        return self._factory(tool_name, payload)


__all__ = [
    "VALID_VENDOR_KINDS",
    "VendorAdapter",
    "VendorAdapterError",
    "StubVendorAdapter",
]

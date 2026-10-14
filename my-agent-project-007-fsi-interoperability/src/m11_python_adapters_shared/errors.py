"""Canonical adapter error codes.

The Python adapter family mirrors the TypeScript SDK's 22-code vocabulary so
M6 / M10 can reason about errors regardless of adapter runtime. Any vendor
error translates into EXACTLY one code here. Unknown failures map to
``vendor_error``.
"""

from __future__ import annotations

from typing import Final


ADAPTER_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "invalid_arguments",
        "vendor_auth_failed",
        "vendor_not_entitled",
        "vendor_invalid_field",
        "vendor_invalid_security",
        "vendor_bad_request",
        "vendor_not_found",
        "vendor_rate_limited",
        "vendor_timeout",
        "vendor_unavailable",
        "vendor_transport_error",
        "vendor_session_lost",
        "vendor_circuit_open",
        "vendor_invalid_json",
        "vendor_error",
        "adapter_not_enabled",
        "adapter_shutting_down",
        "adapter_internal_error",
    }
)

_RETRYABLE: Final[frozenset[str]] = frozenset(
    {
        "vendor_rate_limited",
        "vendor_timeout",
        "vendor_unavailable",
        "vendor_transport_error",
        "vendor_session_lost",
    }
)


def is_retryable_code(code: str) -> bool:
    """Return True iff the canonical error code is safe to retry."""
    return code in _RETRYABLE


class AdapterError(Exception):
    """Canonical adapter exception.

    Carries a stable ``code`` drawn from :data:`ADAPTER_ERROR_CODES` plus optional
    vendor-specific ``vendor_status`` (gRPC status string, HTTP status int, or
    blpapi error code int) for audit visibility.

    Never construct with an unknown code — the constructor raises ``ValueError``
    to keep the vocabulary stable at runtime.
    """

    __slots__ = ("code", "vendor_status", "retryable", "_message")

    def __init__(
        self,
        code: str,
        message: str,
        vendor_status: object | None = None,
        *,
        retryable: bool | None = None,
    ) -> None:
        if code not in ADAPTER_ERROR_CODES:
            raise ValueError(
                f"AdapterError: unknown code {code!r}; must be one of "
                f"{sorted(ADAPTER_ERROR_CODES)}"
            )
        super().__init__(message)
        self.code = code
        self.vendor_status = vendor_status
        # Default retryable from the lookup table when not overridden.
        self.retryable = is_retryable_code(code) if retryable is None else bool(retryable)
        self._message = message

    @property
    def message(self) -> str:
        return self._message

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return (
            f"AdapterError(code={self.code!r}, message={self._message!r}, "
            f"vendor_status={self.vendor_status!r}, retryable={self.retryable!r})"
        )

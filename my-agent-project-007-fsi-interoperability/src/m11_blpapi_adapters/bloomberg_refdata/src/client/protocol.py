"""Swappable seam between the adapter and the Bloomberg SDK.

The adapter code only talks to :class:`BlpapiClientProtocol`. Concrete
implementations:

* :class:`FakeBlpapiClient` (default) — serves deterministic fixtures, used in
  CI and whenever ``BLPAPI_ENABLED`` is false.
* :class:`RealBlpapiClient` — imports the `blpapi` module at class-loading
  time, only instantiated when ``BLPAPI_ENABLED=true``.

Request / response shapes are the adapter's own canonical JSON-friendly types,
NOT vendor Element objects. The real client flattens BLPAPI Elements into
these shapes before returning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class BlpapiRequest:
    """Canonical request shape for all 4 BLPAPI-backed tools.

    ``service`` is always ``"//blp/refdata"`` for v1 — streaming subscriptions
    via ``//blp/mktdata`` are out of scope (spec §12).

    ``operation`` selects the BLPAPI request type:
      * ``ReferenceDataRequest``
      * ``HistoricalDataRequest``
      * ``IntradayTickRequest``

    ``payload`` is the operation-specific body. For each operation the adapter
    side builds this dict; both the real client (which unpacks into BLPAPI
    Elements) and the fake client (which keys into fixtures) consume it.
    """

    service: Literal["//blp/refdata", "//blp/mktdata"]
    operation: Literal[
        "ReferenceDataRequest",
        "HistoricalDataRequest",
        "IntradayTickRequest",
    ]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BlpapiResponse:
    """Canonical response envelope.

    ``data`` is a dict keyed by security identifier (for multi-security
    requests) or a list of rows (for single-security historical / intraday).
    The shape is operation-specific but always JSON-serializable.

    ``partial`` indicates the BLPAPI session delivered only part of the
    response before the caller deadline elapsed. Callers can retry the
    request; no caching happens here.

    ``vendor_response_code`` is the numeric blpapi error code (0 on success).
    """

    data: dict[str, Any]
    partial: bool = False
    vendor_response_code: int = 0


class BlpapiVendorError(Exception):
    """Raised by the Protocol when the vendor returned an error element.

    Carries the blpapi ``errorCode`` (string) + human-readable message. The
    higher-level client translates this to :class:`AdapterError` with a
    canonical code from the mapping table in spec §6.
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        vendor_code: int | None = None,
        vendor_category: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.vendor_code = vendor_code
        self.vendor_category = vendor_category


class BlpapiClientProtocol(ABC):
    """The one-method interface between the adapter and BLPAPI.

    ``execute`` is async. The real client runs the BLPAPI synchronous
    ``session.sendRequest`` + ``session.nextEvent`` loop inside an executor
    so it does not block the FastAPI event loop.
    """

    @abstractmethod
    async def open(self) -> None:
        """Open the underlying session / ensure fixtures are loaded."""

    @abstractmethod
    async def close(self) -> None:
        """Flush + close. Must be idempotent."""

    @abstractmethod
    def healthy(self) -> bool:
        """Synchronous health check (no I/O)."""

    @abstractmethod
    async def execute(self, req: BlpapiRequest) -> BlpapiResponse:
        """Run a single BLPAPI request.

        Raises :class:`BlpapiVendorError` on a vendor-side error element.
        Raises :class:`TimeoutError` on session deadline.
        Raises :class:`ConnectionError` on session-lost / transport failure.
        """

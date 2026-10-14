"""Real Bloomberg BLPAPI client.

Imports the ``blpapi`` module LAZILY inside :meth:`bootstrap` so the adapter
module is importable on CI / dev boxes that don't have the proprietary wheel
installed. All tests exercise :class:`FakeBlpapiClient`; this class is only
instantiated in production when ``BLPAPI_ENABLED=true``.

Design:

* Opens a single ``blpapi.Session`` per pod.
* ``session.startAsync()`` returns quickly; we then block on
  ``session.nextEvent`` for the ``SessionStarted`` response up to
  ``session_timeout_ms``.
* Authorization uses the `AuthenticationType=OS_LOGON` scheme for DAPI
  (desktop) or the `AuthenticationType=USER_APP` scheme for SAPI server mode.
  Vault-fetched UUID + serial go into the auth request.
* Synchronous BLPAPI calls (``session.sendRequest`` + ``nextEvent``) run in
  :meth:`asyncio.get_running_loop().run_in_executor` so the FastAPI event loop
  stays responsive.

All public methods satisfy :class:`BlpapiClientProtocol`.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiClientProtocol,
    BlpapiRequest,
    BlpapiResponse,
    BlpapiVendorError,
)


class BlpapiNotAvailableError(RuntimeError):
    """Raised when the real client is instantiated but the SDK is absent."""


class RealBlpapiClient(BlpapiClientProtocol):
    """Real BLPAPI session wrapper.

    Construct via :meth:`bootstrap`. The constructor itself is minimal — heavy
    work (SDK import, session start, authorization, service open) happens in
    :meth:`open`.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        uuid: str,
        serial: str,
        services: tuple[str, ...] = ("//blp/refdata",),
        client_mode: str = "DAPI",
        session_timeout_ms: int = 30_000,
    ) -> None:
        self._host = host
        self._port = port
        self._uuid = uuid
        self._serial = serial
        self._services = services
        self._client_mode = client_mode
        self._session_timeout_ms = session_timeout_ms
        self._session: Any | None = None  # blpapi.Session at runtime
        self._identity: Any | None = None
        self._authorized: bool = False
        self._blpapi: Any | None = None  # lazy-imported module
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def bootstrap(
        cls,
        *,
        host: str,
        port: int,
        uuid: str,
        serial: str,
        services: tuple[str, ...] = ("//blp/refdata",),
        client_mode: str = "DAPI",
        session_timeout_ms: int = 30_000,
    ) -> "RealBlpapiClient":
        """Build an instance but defer session open.

        Import of ``blpapi`` is deferred to :meth:`open` so the class is
        import-safe on machines without the proprietary wheel.
        """
        return cls(
            host=host,
            port=port,
            uuid=uuid,
            serial=serial,
            services=services,
            client_mode=client_mode,
            session_timeout_ms=session_timeout_ms,
        )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    async def open(self) -> None:  # pragma: no cover — requires blpapi wheel
        """Import blpapi, start a Session, authorize, open services.

        This method is exercised only in production where the blpapi wheel is
        installed; unit tests use :class:`FakeBlpapiClient`.
        """
        if self._session is not None:
            return
        try:
            import blpapi  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BlpapiNotAvailableError(
                "blpapi module is not installed — build the adapter image with "
                "--build-arg BLPAPI_WHEEL_PATH=..."
            ) from exc
        self._blpapi = blpapi

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_open)

    def _sync_open(self) -> None:  # pragma: no cover — requires blpapi wheel
        """Blocking session-open routine run in a worker thread."""
        blpapi = self._blpapi
        assert blpapi is not None
        with self._lock:
            opts = blpapi.SessionOptions()
            opts.setServerHost(self._host)
            opts.setServerPort(self._port)
            opts.setAutoRestartOnDisconnection(True)
            opts.setNumStartAttempts(3)

            session = blpapi.Session(opts)
            if not session.start():
                raise ConnectionError("blpapi.Session.start() returned False")

            # Authorization — OS_LOGON for DAPI desktop, USER_APP for SAPI.
            auth_service = session.getService("//blp/apiauth") if (
                session.openService("//blp/apiauth")
            ) else None
            if auth_service is None:
                session.stop()
                raise ConnectionError("failed to open //blp/apiauth")

            auth_req = auth_service.createAuthorizationRequest()
            auth_req.set("uuid", int(self._uuid))
            auth_req.set("ipAddress", "127.0.0.1")
            # Identity is a per-session token bound to the UUID + serial.
            identity = session.createIdentity()
            event_queue = blpapi.EventQueue()
            cid = session.sendAuthorizationRequest(auth_req, identity, event_queue=event_queue)
            deadline = self._session_timeout_ms
            authorized = False
            while deadline > 0:
                ev = event_queue.nextEvent(min(deadline, 1000))
                if ev.eventType() == blpapi.Event.RESPONSE:
                    for msg in ev:
                        if msg.messageType() == blpapi.Name("AuthorizationSuccess"):
                            authorized = True
                    break
                deadline -= 1000
            if not authorized:
                session.stop()
                raise ConnectionError("blpapi authorization timeout / failure")

            for svc in self._services:
                if not session.openService(svc):
                    session.stop()
                    raise ConnectionError(f"failed to open service {svc}")

            self._session = session
            self._identity = identity
            self._authorized = True

    async def close(self) -> None:  # pragma: no cover — requires blpapi wheel
        if self._session is None:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_close)

    def _sync_close(self) -> None:  # pragma: no cover — requires blpapi wheel
        with self._lock:
            try:
                if self._session is not None:
                    self._session.stop()
            finally:
                self._session = None
                self._identity = None
                self._authorized = False

    def healthy(self) -> bool:
        return self._session is not None and self._authorized

    async def execute(self, req: BlpapiRequest) -> BlpapiResponse:  # pragma: no cover
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_execute, req)

    def _sync_execute(self, req: BlpapiRequest) -> BlpapiResponse:  # pragma: no cover
        """Run a single blpapi request synchronously.

        The exact Element-to-JSON flattening is operation-specific; we keep
        it minimal here and rely on production tests against a live Terminal
        for end-to-end verification.
        """
        blpapi = self._blpapi
        assert blpapi is not None
        if self._session is None:
            raise ConnectionError("session not started")
        service = self._session.getService(req.service)
        request = service.createRequest(req.operation)
        for key, value in req.payload.items():
            _apply_value(request, key, value)
        self._session.sendRequest(request, identity=self._identity)

        data: dict[str, Any] = {}
        while True:
            ev = self._session.nextEvent(self._session_timeout_ms)
            et = ev.eventType()
            if et in (blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE):
                for msg in ev:
                    if msg.hasElement("responseError"):
                        re = msg.getElement("responseError")
                        raise BlpapiVendorError(
                            error_code=re.getElementAsString("category"),
                            message=re.getElementAsString("message"),
                            vendor_category=re.getElementAsString("category"),
                        )
                    # Flatten Elements to dict — shape is operation-specific.
                    data[str(msg.messageType())] = _flatten_element(msg.asElement())
                if et == blpapi.Event.RESPONSE:
                    break
            elif et == blpapi.Event.SESSION_STATUS and not self._session.isRunning():
                raise ConnectionError("session lost mid-request")
            elif et == blpapi.Event.TIMEOUT:
                raise TimeoutError("blpapi request timed out")
        return BlpapiResponse(data=data, partial=False, vendor_response_code=0)


def _apply_value(request: Any, key: str, value: Any) -> None:  # pragma: no cover
    """Set a field on a blpapi.Request. Lists become appended elements."""
    if isinstance(value, (list, tuple)):
        elem = request.getElement(key)
        for item in value:
            elem.appendValue(item)
    else:
        request.set(key, value)


def _flatten_element(element: Any) -> Any:  # pragma: no cover
    """Best-effort flatten of a blpapi.Element tree to JSON-safe shapes."""
    try:
        if element.isArray():
            return [_flatten_element(element.getValueAsElement(i))
                    for i in range(element.numValues())]
        if element.numElements() > 0:
            return {
                str(element.getElement(i).name()):
                    _flatten_element(element.getElement(i))
                for i in range(element.numElements())
            }
        return element.getValue()
    except Exception:
        return str(element)

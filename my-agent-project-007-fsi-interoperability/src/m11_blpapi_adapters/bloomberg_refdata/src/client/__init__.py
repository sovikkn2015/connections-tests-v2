"""Bloomberg refdata client package.

Exposes the :class:`BlpapiClientProtocol` (the swappable seam), both concrete
implementations (:class:`FakeBlpapiClient` and :class:`RealBlpapiClient`), plus
the higher-level :class:`BloombergRefDataClient` which owns the session pool,
circuit breaker, rate limiter, and audit emitter.
"""

from m11_blpapi_adapters.bloomberg_refdata.src.client.protocol import (
    BlpapiClientProtocol,
    BlpapiRequest,
    BlpapiResponse,
    BlpapiVendorError,
)
from m11_blpapi_adapters.bloomberg_refdata.src.client.fake_client import FakeBlpapiClient
from m11_blpapi_adapters.bloomberg_refdata.src.client.real_client import RealBlpapiClient
from m11_blpapi_adapters.bloomberg_refdata.src.client.refdata_client import (
    BloombergRefDataClient,
)
from m11_blpapi_adapters.bloomberg_refdata.src.client.session_pool import (
    BloombergSessionPool,
)

__all__ = [
    "BlpapiClientProtocol",
    "BlpapiRequest",
    "BlpapiResponse",
    "BlpapiVendorError",
    "FakeBlpapiClient",
    "RealBlpapiClient",
    "BloombergRefDataClient",
    "BloombergSessionPool",
]

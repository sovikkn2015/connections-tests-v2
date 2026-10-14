"""Real ICE Data gRPC stub.

Imports ``grpc`` and the generated stubs LAZILY inside :meth:`open` so the
module stays importable on dev / CI boxes that don't have ``grpcio``. Only
instantiated in production when ``ICE_ENABLED=true``.

Design:
* One :class:`grpc.aio.Channel` per tenant, cached on first request.
* Channel credentials = SSL (mTLS client cert + CA) composed with bearer
  metadata call credentials. Tenant-id is included in metadata as
  ``x-ice-tenant`` for vendor-side routing.
* Each RPC converts dict → protobuf → call → protobuf → dict. The
  protobuf schemas are generated from ``proto/ice_data.proto``; in the
  repo-as-shipped we stub the conversion because the proto is vendor-specific
  and regenerated per-deploy.

All public methods satisfy :class:`IceStubProtocol`.
"""

from __future__ import annotations

from typing import Any

from m11_grpc_adapters.ice_data.src.client.protocol import (
    IceStubProtocol,
    IceVendorError,
)


class GrpcNotAvailableError(RuntimeError):
    """Raised when ``grpcio`` is not installed at :meth:`open` time."""


class RealIceStub(IceStubProtocol):
    """gRPC stub backed by grpc.aio.

    Construct with the channel parameters and Vault-loaded secrets. :meth:`open`
    must be called before any RPC. Subsequent :meth:`open` calls with the same
    tenant_id are idempotent; different tenant_ids each cache their own
    channel.
    """

    _DEFAULT_CHANNEL_OPTIONS = (
        ("grpc.keepalive_time_ms", 30_000),
        ("grpc.keepalive_timeout_ms", 10_000),
        ("grpc.keepalive_permit_without_calls", 1),
        ("grpc.http2.max_pings_without_data", 0),
        ("grpc.max_send_message_length", 16 * 1024 * 1024),
        ("grpc.max_receive_message_length", 64 * 1024 * 1024),
    )

    def __init__(
        self,
        *,
        target: str,
        mtls_cert: bytes,
        mtls_key: bytes,
        mtls_ca: bytes,
        bearer_token: str,
        pool_size: int = 4,
    ) -> None:
        self._target = target
        self._mtls_cert = mtls_cert
        self._mtls_key = mtls_key
        self._mtls_ca = mtls_ca
        self._bearer_token = bearer_token
        self._pool_size = max(1, int(pool_size))
        # Lazy-imported module + stub cache.
        self._grpc: Any | None = None
        self._channels: dict[str, Any] = {}  # tenant_id -> Channel
        self._closed = False

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    async def open(self, tenant_id: str) -> None:  # pragma: no cover — requires grpc
        if self._closed:
            raise ConnectionError("ICE stub is closed")
        if tenant_id in self._channels:
            return
        if self._grpc is None:
            try:
                import grpc  # type: ignore[import-not-found]
            except ImportError as exc:
                raise GrpcNotAvailableError(
                    "grpcio is not installed — install the adapter image built "
                    "with grpcio in its dependency set"
                ) from exc
            self._grpc = grpc
        # Evict the least-recently-added channel when pool is full.
        if len(self._channels) >= self._pool_size:
            oldest = next(iter(self._channels))
            old_channel = self._channels.pop(oldest)
            try:
                await old_channel.close()
            except Exception:
                pass

        grpc = self._grpc
        ssl_creds = grpc.ssl_channel_credentials(
            root_certificates=self._mtls_ca,
            private_key=self._mtls_key,
            certificate_chain=self._mtls_cert,
        )

        def _auth_metadata(ctx: Any, cb: Any) -> None:
            cb(
                (
                    ("authorization", f"Bearer {self._bearer_token}"),
                    ("x-ice-tenant", tenant_id),
                ),
                None,
            )

        bearer_creds = grpc.metadata_call_credentials(_auth_metadata)
        composite = grpc.composite_channel_credentials(ssl_creds, bearer_creds)
        channel = grpc.aio.secure_channel(
            self._target,
            composite,
            options=self._DEFAULT_CHANNEL_OPTIONS,
        )
        self._channels[tenant_id] = channel

    async def close(self) -> None:  # pragma: no cover — requires grpc
        self._closed = True
        channels = list(self._channels.values())
        self._channels.clear()
        for ch in channels:
            try:
                await ch.close()
            except Exception:
                pass

    def healthy(self) -> bool:
        return not self._closed and len(self._channels) > 0

    async def get_market_data_snapshot(  # pragma: no cover — requires grpc
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._invoke(tenant_id, "GetMarketDataSnapshot", request)

    async def get_trade_tape(  # pragma: no cover — requires grpc
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._invoke(tenant_id, "GetTradeTape", request)

    async def get_reference_data(  # pragma: no cover — requires grpc
        self, tenant_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._invoke(tenant_id, "GetReferenceData", request)

    async def _invoke(  # pragma: no cover — requires grpc + generated stubs
        self, tenant_id: str, rpc_name: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Placeholder invocation — real implementation converts via pb2 stubs.

        Shipped as a stub because the protobuf contract is vendor-specific and
        regenerated per-deploy. Production override supplies generated classes
        and a real unary_unary call. The method shape mirrors what the generated
        stub produces.
        """
        if tenant_id not in self._channels:
            raise ConnectionError(f"no channel for tenant {tenant_id!r}")
        raise NotImplementedError(
            f"{rpc_name} real stub requires generated pb2 stubs; wire them in "
            "the production image via scripts/gen_ice_stubs.sh"
        )

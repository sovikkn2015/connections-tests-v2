"""ICE Data Services gRPC adapter.

Tools:
* ``ice.market_data_snapshot``
* ``ice.trade_tape``
* ``ice.reference_data``

See :file:`.kiro/specs/m11-grpc-adapter.md`.
"""

from m11_grpc_adapters.ice_data.src.startup import bootstrap
from m11_grpc_adapters.ice_data.src.tools import TOOL_NAMES

__all__ = ["bootstrap", "TOOL_NAMES"]

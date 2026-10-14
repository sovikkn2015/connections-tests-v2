"""Bloomberg reference-data adapter (BLPAPI protocol).

Entry points:
* :func:`src.server.build_app` — FastAPI MCP server factory.
* :func:`src.startup.bootstrap` — wire config, session, tools. Returns the
  bootstrap result used by the FastAPI app and by tests.

Public tools:
* ``bloomberg.reference_data``
* ``bloomberg.historical_data``
* ``bloomberg.intraday_tick``
* ``bloomberg.corporate_actions``

See :file:`.kiro/specs/m11-blpapi-adapter.md` for the contract.
"""

from m11_blpapi_adapters.bloomberg_refdata.src.startup import bootstrap
from m11_blpapi_adapters.bloomberg_refdata.src.tools import TOOL_NAMES

__all__ = ["bootstrap", "TOOL_NAMES"]

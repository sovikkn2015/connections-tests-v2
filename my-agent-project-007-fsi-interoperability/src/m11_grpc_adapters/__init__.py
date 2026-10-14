"""M11 gRPC adapter family.

Current members:
* ``ice_data`` — ICE Data Services market-data gRPC API (reference implementation).

Each member is an independently deployable MCP server container per Steering
Rule 10 (one adapter = one container). Python 3.12+ with ``grpcio`` (imported
lazily so dev / CI environments without the wheel can still run the fake-backed
tests).
"""

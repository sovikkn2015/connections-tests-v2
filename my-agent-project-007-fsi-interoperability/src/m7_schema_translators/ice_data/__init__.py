"""ICE Data (Intercontinental Exchange market data) M7 translators.

M11-gRPC adapter emits reference + quote payloads modelled on ICE Data's
Consolidated Feed REST schema. This package canonicalizes those into
M3 :class:`SecurityProfile` and :class:`Quote`.
"""

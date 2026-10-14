"""
Cross-module: M11 adapter VENDOR_API_VERSION == M7 translator VENDOR_API_VERSION.

Spec AC10.1 + Task 19. Each M11-REST adapter declares the vendor-API
version it speaks; every M7 translator declares the version it canonicalizes.
Any drift between them breaks the round-trip.

This test reads M7's `VENDOR_API_VERSION` constants directly and compares
against a local table of M11 adapter expected values.

M11 adapter constants are authored in TypeScript (src/config.ts), so this
Python test hard-codes the expected values and the sister test
`test_sfdc_adapter_version_constant_matches_expected` (run in TS land via
vitest) keeps the TS side honest.
"""

from __future__ import annotations

import importlib

import pytest

# Expected versions per M11 adapter.
EXPECTED: dict[str, str] = {
    "salesforce_fsc": "v59.0",
    "orion": "v2.0",
    "emoney": "v2",
    "schwab": "v1",
}

# Mapping (vendor → at least one M7 module exposing VENDOR_API_VERSION).
M7_MODULES: dict[str, str] = {
    "salesforce_fsc": "m7_schema_translators.salesforce_fsc.client",
    "orion": "m7_schema_translators.orion.holding",
    "emoney": "m7_schema_translators.emoney.plan_summary",
    "schwab": "m7_schema_translators.schwab.holding",
}


@pytest.mark.parametrize("vendor", sorted(EXPECTED.keys()))
def test_m7_version_matches_m11_expected(vendor: str) -> None:
    module_path = M7_MODULES[vendor]
    mod = importlib.import_module(module_path)
    m7_version = getattr(mod, "VENDOR_API_VERSION")
    assert m7_version == EXPECTED[vendor], (
        f"M11 expects {vendor} VENDOR_API_VERSION={EXPECTED[vendor]!r}, "
        f"but M7 module {module_path} declares {m7_version!r}"
    )

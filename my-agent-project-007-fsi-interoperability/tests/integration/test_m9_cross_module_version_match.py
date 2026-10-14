"""
M9 Task 19 -- Cross-module version-match test.

Fix 5: M9 taxonomy tool-kind names must be a subset of M6 registered tools,
and pipeline-kind names must be a subset of M8 PIPELINE_NAMES.

xfail=strict=False -- when M6/M8 land their manifests, these upgrade to pass.
"""

from __future__ import annotations

import pytest

from m9_intent_router import IntentCategory
from m9_intent_router.taxonomy import TAXONOMY_DISPATCH


@pytest.mark.xfail(
    reason="PENDING-CONFIRM-WITH-M6 -- M6 Phase 2 composed-tool manifest",
    strict=False,
)
def test_tool_kind_names_subset_of_m6_registered():
    # M6 REGISTERED_TOOLS not yet exported -- xfails on ImportError.
    import importlib

    mod = importlib.import_module("m6_mcp_gateway")
    registered = getattr(mod, "REGISTERED_TOOLS", None)
    if registered is None:
        raise ImportError("REGISTERED_TOOLS not yet exported by M6")
    m9_tool_names = {
        t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "tool"
    }
    missing = m9_tool_names - set(registered)
    assert not missing, f"M9 references tools not in M6 registry: {missing}"


@pytest.mark.xfail(
    reason="PENDING-CONFIRM-WITH-M8 -- M8 v0.1.0 PIPELINE_NAMES constant",
    strict=False,
)
def test_pipeline_kind_names_subset_of_m8_pipeline_names():
    import importlib

    mod = importlib.import_module("m8_research_pipeline")
    pipeline_names = getattr(mod, "PIPELINE_NAMES", None)
    if pipeline_names is None:
        raise ImportError("PIPELINE_NAMES not yet exported by M8")
    m9_pipeline_names = {
        t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "pipeline"
    }
    missing = m9_pipeline_names - set(pipeline_names)
    assert not missing, (
        f"M9 references pipelines not exported by M8: {missing}"
    )


def test_taxonomy_has_expected_tool_and_pipeline_names():
    """Sanity -- our own names remain the ones we expect."""
    tool_names = {
        t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "tool"
    }
    pipeline_names = {
        t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "pipeline"
    }
    assert "sfdc.fetch_client" in tool_names
    assert "orion.fetch_transactions" in tool_names
    assert "m8.research_pipeline_1" in pipeline_names
    assert "m8.research_pipeline_3" in pipeline_names
    assert (
        TAXONOMY_DISPATCH[IntentCategory.COMPLIANCE_QUESTION].kind == "escalate"
    )

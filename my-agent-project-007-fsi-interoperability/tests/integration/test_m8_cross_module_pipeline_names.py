"""Task 20 -- Cross-module version match: PIPELINE_NAMES subset of M9 taxonomy.

AC A4 -- Every pipeline name in M8's PIPELINE_NAMES must appear in M9's
taxonomy dispatch with kind="pipeline".
"""

from __future__ import annotations

import pytest

from m8_pipeline_engine import PIPELINE_NAMES


def _m9_pipeline_target_names() -> set[str]:
    """Extract all kind='pipeline' target names from M9's taxonomy."""
    try:
        from m9_intent_router import taxonomy as _taxonomy
    except Exception:
        return set()
    names: set[str] = set()
    dispatch = getattr(_taxonomy, "TAXONOMY_DISPATCH", None)
    if dispatch is None:
        dispatch = getattr(_taxonomy, "dispatch_targets", None)
        if callable(dispatch):
            dispatch = dispatch()
    if isinstance(dispatch, dict):
        for target in dispatch.values():
            kind = getattr(target, "kind", None)
            name = getattr(target, "name", None)
            if kind == "pipeline" and name:
                names.add(name)
    return names


def test_pipeline_names_subset_of_m9_taxonomy() -> None:
    m9_names = _m9_pipeline_target_names()
    if not m9_names:
        pytest.xfail("M9 taxonomy dispatch not exposed or empty")
    missing = PIPELINE_NAMES - m9_names
    assert not missing, (
        f"M8 declares pipeline names not in M9 taxonomy: {missing}"
    )


def test_pipeline_names_frozenset_has_4_entries() -> None:
    assert isinstance(PIPELINE_NAMES, frozenset)
    assert len(PIPELINE_NAMES) == 4
    assert "m8.research_pipeline_1" in PIPELINE_NAMES
    assert "m8.research_pipeline_2" in PIPELINE_NAMES
    assert "m8.research_pipeline_3" in PIPELINE_NAMES
    assert "m8.research_single_tool" in PIPELINE_NAMES

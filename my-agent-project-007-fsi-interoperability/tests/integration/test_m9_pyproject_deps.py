"""
M9 Task 17 -- pyproject.toml dependency shape.

AC12.7.
"""

from __future__ import annotations

import pathlib

PYPROJECT = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_pyproject_exists():
    assert PYPROJECT.exists()


def test_pyproject_no_forbidden_framework_deps():
    """AC12.7 -- no langchain, langgraph, anthropic, openai, prefect."""
    content = PYPROJECT.read_text().lower()
    for forbidden in (
        "langchain",
        "langgraph",
        "anthropic",
        "openai",
        "prefect",
        "airflow",
        "crewai",
    ):
        assert forbidden not in content, (
            f"pyproject.toml must not reference {forbidden}"
        )


def test_pyproject_no_m3_schema_registry_dep():
    """AC12.7 v0.2.0 -- m3-schema-registry REMOVED."""
    content = PYPROJECT.read_text()
    assert "m3-schema-registry" not in content


def test_core_deps_present():
    """pydantic required."""
    content = PYPROJECT.read_text()
    assert "pydantic" in content

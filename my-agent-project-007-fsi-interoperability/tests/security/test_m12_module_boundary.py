"""
M12 Supervisor -- module boundary AST scan.

M12 is the thin seam between channel and specialists. It may ONLY
import from:
  - m1_identity  (to validate AidClaims shape)
  - m5_config_loader  (Archetype, Runtime enums used by M9 RouterContext)
  - m8_pipeline_engine  (run, PipelineResult)
  - m9_intent_router  (route, RouterContext, etc.)

Everything upstream of M12's seam (m2/m3/m4/m6/m7/m10/m11/m13,
compliance.*) is BLOCKED.

See the M12 task prompt "Rules" section.
"""

from __future__ import annotations

import ast
import pathlib

SRC_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m12_supervisor"
)


def _walk_py_files() -> list[pathlib.Path]:
    return sorted(
        p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in str(p)
    )


def test_src_dir_exists():
    assert SRC_ROOT.is_dir(), f"M12 src dir missing: {SRC_ROOT}"
    assert len(_walk_py_files()) > 0


FORBIDDEN_MODULE_PREFIXES = (
    "m2_",
    "m3_",
    "m4_",
    "m6_",
    "m7_",
    "m10_",
    "m11_",
    "m13_",
    "compliance.",
)


def test_no_forbidden_cross_module_imports():
    violations: list[tuple[str, str]] = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in FORBIDDEN_MODULE_PREFIXES:
                    if node.module.startswith(prefix):
                        violations.append((py.name, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in FORBIDDEN_MODULE_PREFIXES:
                        if alias.name.startswith(prefix):
                            violations.append((py.name, alias.name))
    assert not violations, (
        f"M12 has forbidden cross-module imports: {violations}"
    )


def test_positive_allowlist_is_m1_m5_m8_m9_only():
    """Intra-project imports must come only from the M12 allowlist."""
    ALLOWED = (
        "m1_identity",
        "m5_config_loader",
        "m8_pipeline_engine",
        "m9_intent_router",
        "m12_supervisor",
    )
    violations: list[tuple[str, str]] = []
    for py in _walk_py_files():
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if mod.startswith("m") and mod[1:2].isdigit():
                    top = mod.split(".", 1)[0]
                    if top not in ALLOWED:
                        violations.append((py.name, mod))
    assert not violations, (
        f"M12 has disallowed intra-project imports: {violations}"
    )


def test_m12_never_imports_m6():
    """Rule 7 boundary: tool dispatch is the channel's job."""
    for py in _walk_py_files():
        content = py.read_text()
        assert "m6_mcp_gateway" not in content, (
            f"{py.name} contains forbidden m6_mcp_gateway reference"
        )


def test_m12_never_imports_m10():
    """M10 audit is owned by M8/M9 per their own channels."""
    for py in _walk_py_files():
        content = py.read_text()
        assert "m10_audit_logger" not in content, (
            f"{py.name} contains forbidden m10_audit_logger reference"
        )


def test_m12_public_api_surface():
    """The public API is the core 6 names + specialist registration.

    v0.2.0 adds SPECIALIST_DISPATCH and get_specialist for Phase 3
    Execution / Onboarding wiring.
    """
    import m12_supervisor

    assert set(m12_supervisor.__all__) == {
        "dispatch",
        "SupervisorResult",
        "build_router_context",
        "build_pipeline_state",
        "SCHEMA_VERSION",
        "VALID_REASON_CODES",
        "SPECIALIST_DISPATCH",
        "get_specialist",
    }
    assert m12_supervisor.SCHEMA_VERSION == "0.2.0"

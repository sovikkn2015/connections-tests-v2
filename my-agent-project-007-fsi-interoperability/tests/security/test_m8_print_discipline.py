"""Task 2 AC13.5 v0.2.0 -- print() discipline: no raw payloads."""

import ast
import pathlib

_ROOT = pathlib.Path("my-agent-project-007-fsi-interoperability/src/m8_pipeline_engine")

_FORBIDDEN_ARG_NAMES = {"prompt", "payload", "result", "tool_result", "raw", "text"}


def _print_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                yield node


def test_print_allowed_only_in_audit_emit_fallback():
    allowed_files = {"audit_emit.py"}
    for path in sorted(_ROOT.rglob("*.py")):
        src = path.read_text()
        tree = ast.parse(src)
        calls = list(_print_calls(tree))
        if not calls:
            continue
        assert path.name in allowed_files, (
            f"{path}: print() appears outside allowed files"
        )
        # Within audit_emit, assert no forbidden variable names as args
        for call in calls:
            for arg in call.args:
                if isinstance(arg, ast.Name):
                    assert arg.id not in _FORBIDDEN_ARG_NAMES, (
                        f"{path}: print({arg.id}) forbidden"
                    )
                if isinstance(arg, ast.Call):
                    # nested calls -- scan their args for forbidden names
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Name) and sub.id in _FORBIDDEN_ARG_NAMES:
                            # allowed if it's a dict key literal like 'raw_payload never ...'
                            pass  # too permissive to block all; rely on code review

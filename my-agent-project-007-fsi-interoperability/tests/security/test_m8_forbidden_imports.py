"""Task 2 AC13.1 -- Forbidden stdlib / third-party imports."""

import ast
import pathlib
import pytest

_BANNED = frozenset({
    "logging",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "langchain",
    "langchain_aws",
    "langchain_community",
    "anthropic",
    "openai",
    "warnings",
    "tempfile",
    "socket",
    "subprocess",
    "grpc",
    "celery",
    "prefect",
    "airflow",
    "crewai",
})

_ROOT = pathlib.Path("my-agent-project-007-fsi-interoperability/src/m8_pipeline_engine")


def _iter_modules():
    for p in sorted(_ROOT.rglob("*.py")):
        yield p


@pytest.mark.parametrize("path", list(_iter_modules()), ids=lambda p: p.name)
def test_no_banned_imports(path: pathlib.Path):
    src = path.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top not in _BANNED, f"{path}: banned import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top not in _BANNED, f"{path}: banned ImportFrom {node.module!r}"


def test_boto3_scope():
    """AC13.3 -- boto3 only in llm_client, hitl, checkpointer."""
    allowed = {"llm_client.py", "hitl.py", "checkpointer.py"}
    for path in _iter_modules():
        if path.name in allowed:
            continue
        src = path.read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("boto3"), (
                        f"{path}: boto3 outside allowed scope"
                    )


def test_urllib_request_scope():
    """AC13.4 -- urllib.request only in gateway_client, audit_client."""
    allowed = {"gateway_client.py", "audit_client.py"}
    for path in _iter_modules():
        if path.name in allowed:
            continue
        src = path.read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("urllib.request"):
                    raise AssertionError(
                        f"{path}: urllib.request outside allowed scope"
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("urllib.request"):
                        raise AssertionError(
                            f"{path}: urllib.request outside allowed scope"
                        )

"""
M12 Supervisor -- hardcoded credential scan (Rule 16).

No literal assignments matching credential shapes. No AWS keys,
OpenAI tokens, Slack tokens, PEM blocks, connection strings, or
password-shaped assignments.
"""

from __future__ import annotations

import pathlib
import re

SRC_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m12_supervisor"
)

_CRED_PAT = re.compile(
    r"(?i)(api_key|apikey|secret|password|access_key|aws_access_key_id|"
    r"aws_secret_access_key)\s*=\s*['\"][^'\"]+['\"]"
)

_SECRET_VALUE_PATTERNS = [
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[bp]-[A-Za-z0-9\-]+"),
    re.compile(r"-----BEGIN"),
    re.compile(r"postgresql://[^ '\"]+:[^ '\"]+@"),
    re.compile(r"mongodb://[^ '\"]+:[^ '\"]+@"),
]


def test_no_hardcoded_creds_in_src():
    for py in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        content = py.read_text()
        matches = _CRED_PAT.findall(content)
        assert not matches, (
            f"{py.name} contains credential-shaped assignment: {matches}"
        )


def test_no_secret_value_patterns_in_src():
    for py in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        content = py.read_text()
        for pat in _SECRET_VALUE_PATTERNS:
            assert not pat.search(content), (
                f"{py.name} contains forbidden secret-shaped literal "
                f"matching {pat.pattern!r}"
            )

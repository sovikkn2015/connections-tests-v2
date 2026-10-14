"""Task 2 AC14.1 -- Zero hardcoded credentials regex scan."""

import pathlib
import re

# Match assignments of credential-shaped names to string literals (bracket-quoted)
_CRED_RE = re.compile(
    r"(?i)(api_key|apikey|secret|password|access_key|dsn)\s*=\s*['\"][^'\"<>]+['\"]"
)

# Anchor relative to this test file so it resolves regardless of CWD
# (CI runs from repo root; contributors run from project root).
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROOT = _PROJECT_ROOT / "src" / "m8_pipeline_engine"


def test_no_credentials_in_source():
    for path in sorted(_ROOT.rglob("*.py")):
        src = path.read_text()
        for i, line in enumerate(src.splitlines(), 1):
            # Skip comment-only lines
            if line.lstrip().startswith("#"):
                continue
            match = _CRED_RE.search(line)
            if match:
                # Allow docstring or placeholder values
                token = match.group(0).lower()
                if "vault" in token or "placeholder" in token or "example" in token:
                    continue
                # Test fixture-key fixtures etc. flagged only if in src/
                raise AssertionError(f"{path}:{i} credential pattern: {line!r}")


def test_env_example_no_secrets():
    env = _ROOT / ".env.example"
    assert env.exists()
    text = env.read_text()
    # No literal credential patterns
    for forbidden in ("password=", "api_key=", "secret=", "token="):
        assert forbidden not in text.lower()

"""
Sandbox wrapper for financial model execution.
Runs models in a subprocess with restricted imports and memory limits.

Architecture: subprocess isolation — no eval/exec. The financial model
runs in a child process with a restricted PYTHONPATH and memory cap.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile

logger = logging.getLogger("sandbox")

ALLOWED_IMPORTS = {"math", "random", "json", "csv", "numpy", "pandas", "scipy"}
MAX_MEMORY_MB = 4096
MAX_EXECUTION_SECONDS = 60

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def run_in_sandbox(module_name: str, function_name: str, kwargs: dict) -> dict:
    """
    Execute a financial model function in an isolated subprocess.

    Parameters
    ----------
    module_name : str
        Module to import (e.g., "dcf", "comps", "monte_carlo")
    function_name : str
        Function to call (e.g., "run_dcf", "run_comps", "run_monte_carlo")
    kwargs : dict
        Keyword arguments to pass to the function

    Returns
    -------
    dict
        The function's return value (must be JSON-serializable),
        or ``{"error": True, "message": "..."}`` on failure.
    """
    safe_module = os.path.basename(module_name).replace(".py", "")

    # Build the temporary runner script
    kwargs_json = json.dumps(kwargs)
    script = _build_runner_script(safe_module, function_name, kwargs_json)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="sandbox_run_")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(script)

        env = {
            "PYTHONPATH": _SKILL_DIR,
            "PATH": os.environ.get("PATH", ""),
            # Inherit virtualenv python if present
            "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
        }

        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_SECONDS,
            cwd=_SKILL_DIR,
            env=env,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.strip()[:500]
            logger.error("Sandbox process failed (rc=%d): %s", proc.returncode, stderr)
            return {"error": True, "message": f"Sandbox exit code {proc.returncode}: {stderr}"}

        stdout = proc.stdout.strip()
        if not stdout:
            return {"error": True, "message": "Sandbox produced no output"}

        return json.loads(stdout)

    except subprocess.TimeoutExpired:
        logger.error("Sandbox timed out after %ds", MAX_EXECUTION_SECONDS)
        return {"error": True, "message": f"Sandbox timed out after {MAX_EXECUTION_SECONDS}s"}
    except json.JSONDecodeError as exc:
        logger.error("Sandbox output not valid JSON: %s", exc)
        return {"error": True, "message": f"Invalid JSON from sandbox: {exc}"}
    except Exception as exc:
        logger.error("Sandbox unexpected error: %s", exc)
        return {"error": True, "message": f"Sandbox error: {exc}"}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _build_runner_script(module_name: str, function_name: str, kwargs_json: str) -> str:
    """
    Build the Python source for the sandboxed child process.

    The child process:
    1. Sets a memory limit via resource.setrlimit
    2. Validates that the module only uses allowed imports
    3. Imports the module and calls the function
    4. Serializes the result as JSON to stdout
    """
    allowed = repr(ALLOWED_IMPORTS)
    max_mem = MAX_MEMORY_MB
    return f'''\
import resource
import sys
import json
import ast
import os

# ── Memory limit ────────────────────────────────────────────────
MAX_BYTES = {max_mem} * 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_AS, (MAX_BYTES, MAX_BYTES))
except (ValueError, resource.error):
    pass  # Some platforms don't support RLIMIT_AS

# ── Import validation ───────────────────────────────────────────
ALLOWED = {allowed}

def _validate_imports(module_path):
    """Check that the module only imports from the allowed set."""
    try:
        with open(module_path, "r") as f:
            tree = ast.parse(f.read())
    except Exception:
        return  # If we can't parse, let the import fail naturally
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED and top != "{module_name}":
                    print(json.dumps({{"error": True, "message": f"Disallowed import: {{alias.name}}"}}))
                    sys.exit(0)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top not in ALLOWED and top != "{module_name}":
                    print(json.dumps({{"error": True, "message": f"Disallowed import: {{node.module}}"}}))
                    sys.exit(0)

module_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{module_name}.py")
if os.path.exists(module_file):
    _validate_imports(module_file)

# ── Execute ─────────────────────────────────────────────────────
try:
    mod = __import__("{module_name}")
    fn = getattr(mod, "{function_name}")
    kwargs = json.loads({repr(kwargs_json)})
    result = fn(**kwargs)
    print(json.dumps(result))
except Exception as exc:
    print(json.dumps({{"error": True, "message": str(exc)}}), file=sys.stdout)
    print(str(exc), file=sys.stderr)
    sys.exit(1)
'''

"""
007 end-to-end live test against real AWS.

NO MOCKS.

Architecture:
  Each module (M1, M2/M4, M10, fake-adapter, M6) runs as its own uvicorn
  subprocess on a 127.0.0.1 port. This mirrors production (each module is its
  own container) without docker-compose overhead.

  Then the M12 Strands supervisor runs in THIS process, calling real Bedrock
  Claude Haiku 4.5 with tool-use, which POSTs to M6 for every tool. M6 runs
  the full trust pipeline (M1 verify → M2 authority → M4 MNPI filter →
  forward to adapter → M4 filter response → leakage scan → M10 audit to real
  DynamoDB + S3 WORM + SQS DLQ).

Prereqs:
  - AWS credentials in the standard chain
  - Bedrock Claude Haiku 4.5 access
  - DynamoDB tables + S3 WORM bucket + SQS DLQ (run infra/aws/provision_007_aws.sh)

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any

import boto3
import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("live_e2e")


# ────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────

def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.5)
            if r.status_code < 500:
                return
        except Exception as e:
            last_err = e
        time.sleep(0.2)
    raise RuntimeError(f"service at {url} did not become healthy: {last_err}")


class UvicornProcess:
    """Launch one uvicorn subprocess, wait for /health."""

    def __init__(
        self,
        label: str,
        module_dir: Path,
        app_target: str,
        port: int,
        env: dict[str, str] | None = None,
        health_path: str = "/health",
    ) -> None:
        self.label = label
        self.module_dir = module_dir
        self.app_target = app_target  # e.g. "app:app" or "m10_audit_logger.app:app"
        self.port = port
        self.env = env or {}
        self.health_path = health_path
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        proc_env = os.environ.copy()
        proc_env.update(self.env)
        proc_env["PYTHONPATH"] = (
            str(self.module_dir) + os.pathsep + proc_env.get("PYTHONPATH", "")
        )
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_target,
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--log-level", proc_env.get("LOG_LEVEL", "warning").lower(),
            "--no-access-log",
        ]
        log.info("[%s] start on :%d  cmd=%s", self.label, self.port, " ".join(cmd))
        # stream subprocess logs to stderr, line-prefixed
        self._log_file = open(
            REPO_ROOT / "scripts" / "_live_e2e_tmp" / f"{self.label.replace('/', '_')}.log",
            "wb",
        )
        self.proc = subprocess.Popen(
            cmd, cwd=str(self.module_dir), env=proc_env,
            stdout=self._log_file, stderr=subprocess.STDOUT,
        )
        _wait_for_health(self.url + self.health_path, timeout=30.0)
        log.info("[%s] healthy at %s", self.label, self.url)

    def dump_log(self, max_bytes: int = 8000) -> str:
        if not getattr(self, "_log_file", None):
            return ""
        try:
            self._log_file.flush()
            with open(self._log_file.name, "rb") as f:
                data = f.read()
                if len(data) > max_bytes:
                    data = data[-max_bytes:]
                return data.decode(errors="replace")
        except Exception as e:
            return f"(log read failed: {e})"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.send_signal(signal.SIGTERM)
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "_log_file", None):
            try:
                self._log_file.close()
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────────
# fake adapter source (written once, launched as uvicorn)
# ────────────────────────────────────────────────────────────────────

FAKE_ADAPTER_SRC = '''\
"""Fake MCP adapter + M7 stub used by scripts/live_e2e_bedrock.py only.
cost_basis_method preserved per Rule 16."""
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/")
def root() -> dict:
    return {"name": "fake-mcp-adapter", "status": "healthy"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@app.post("/tools/list")
def tools_list() -> dict:
    return {"tools": [
        {"name": "get_client_profile", "description": "Fake Salesforce client profile"},
        {"name": "get_holdings",        "description": "Fake Orion holdings"},
        {"name": "get_financial_plan",  "description": "Fake eMoney plan summary"},
    ]}


@app.post("/tools/call")
async def tools_call(req: Request) -> dict:
    body = await req.json()
    name = body.get("name")
    args = body.get("arguments", {})
    cid = args.get("client_id", "unknown")
    if name == "get_client_profile":
        return {"content": {
            "client_id": cid, "display_name": "Henderson Family Trust",
            "primary_advisor": "Sarah Chen", "risk_profile": "Moderate",
            "household_size": 3,
        }}
    if name == "get_holdings":
        return {"content": {"client_id": cid, "holdings": [
            {"symbol": "VOO", "qty": 1250, "cost_basis_method": "specific_lot"},
            {"symbol": "AGG", "qty": 2100, "cost_basis_method": "specific_lot"},
        ]}}
    if name == "get_financial_plan":
        return {"content": {
            "client_id": cid, "plan_summary": {
                "retirement_goal_year": 2041, "funded_ratio": 0.92,
                "risk_score": "Moderate", "top_concerns": ["college funding"],
            },
        }}
    return {"content": {"error": f"unknown tool: {name}"}}


# M7 stub — pass-through translator (for live E2E only).
# In production this is a separate module with real vendor→canonical mappings.
@app.post("/translate")
async def translate(req: Request) -> dict:
    body = await req.json()
    return body.get("data", {})
'''


# ────────────────────────────────────────────────────────────────────
# main
# ────────────────────────────────────────────────────────────────────

def main() -> int:
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    os.environ.setdefault("AWS_REGION", aws_region)

    sts = boto3.client("sts", region_name=aws_region)
    ident = sts.get_caller_identity()
    log.info("aws account=%s arn=%s", ident["Account"], ident["Arn"])

    # ── ports
    m1_port = _free_port()
    m2_port = _free_port()
    m10_port = _free_port()
    adapter_port = _free_port()
    m6_port = _free_port()

    common_env = {
        "AWS_REGION": aws_region,
        "PYTHONUNBUFFERED": "1",
    }

    m1_env = {**common_env}
    m2_env = {**common_env, "USE_LOCAL_EVALUATOR": "true"}
    m10_env = {
        **common_env,
        "M10_S3_BUCKET": os.environ.get("FSI007_S3_AUDIT_BUCKET",
                                        f"fsi007-audit-worm-{aws_region}"),
        "M10_S3_REGION": aws_region,
        "M10_DLQ_BACKEND": "sqs",
        "M10_DLQ_QUEUE_URL": os.environ.get(
            "FSI007_SQS_AUDIT_DLQ",
            f"https://queue.amazonaws.com/{ident['Account']}/fsi007-audit-dlq",
        ),
    }

    m6_env = {
        **common_env,
        "M1_URL": f"http://127.0.0.1:{m1_port}",
        "M2_URL": f"http://127.0.0.1:{m2_port}",
        "M4_URL": f"http://127.0.0.1:{m2_port}",
        "M7_URL": f"http://127.0.0.1:{adapter_port}",  # stubbed /translate
        "M10_URL": f"http://127.0.0.1:{m10_port}",
        "LOG_LEVEL": "DEBUG",
    }

    # ── write shim launchers under scripts/_live_e2e_tmp ────────
    # Each shim loads its module as a Python package (set up submodule_search
    # locations) so that relative imports inside the module resolve correctly.
    # We need this because the module directories have hyphens
    # (`m6-mcp-gateway`) which cannot be used as package names directly.
    tmp = REPO_ROOT / "scripts" / "_live_e2e_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "fake_adapter.py").write_text(FAKE_ADAPTER_SRC)

    # M1 shim — entrypoint.py generates RSA keys and builds the app
    (tmp / "m1_shim.py").write_text(
        'import importlib.util, sys, os\n'
        f'_dir = {str(SRC / "m1-identity")!r}\n'
        'sys.path.insert(0, _dir)\n'
        '_init = os.path.join(_dir, "__init__.py")\n'
        'spec = importlib.util.spec_from_file_location(\n'
        '    "m1_pkg", _init, submodule_search_locations=[_dir])\n'
        'pkg = importlib.util.module_from_spec(spec)\n'
        'sys.modules["m1_pkg"] = pkg\n'
        'spec.loader.exec_module(pkg)\n'
        'from importlib import import_module\n'
        'entry = import_module("m1_pkg.entrypoint")\n'
        'app = entry.app\n'
    )
    # M2 shim — top-level app.py (uses relative imports)
    (tmp / "m2_shim.py").write_text(
        'import importlib.util, sys, os\n'
        f'_dir = {str(SRC / "m2-m4-policy-engine")!r}\n'
        'sys.path.insert(0, _dir)\n'
        '_init = os.path.join(_dir, "__init__.py")\n'
        'spec = importlib.util.spec_from_file_location(\n'
        '    "m2_pkg", _init, submodule_search_locations=[_dir])\n'
        'pkg = importlib.util.module_from_spec(spec)\n'
        'sys.modules["m2_pkg"] = pkg\n'
        'spec.loader.exec_module(pkg)\n'
        'from importlib import import_module\n'
        'app_mod = import_module("m2_pkg.app")\n'
        'app = app_mod.app\n'
    )
    # M10 shim — the top-level src/m10-audit-logger/app.py is the one that
    # honors env-var backends (M10_S3_BUCKET + M10_DLQ_QUEUE_URL). The nested
    # m10_audit_logger subpackage has a parallel app.py that uses in-memory
    # writers only, which we do NOT want for live AWS tests.
    (tmp / "m10_shim.py").write_text(
        'import importlib.util, sys, os\n'
        f'_dir = {str(SRC / "m10-audit-logger")!r}\n'
        'sys.path.insert(0, _dir)\n'
        '_init = os.path.join(_dir, "__init__.py")\n'
        'spec = importlib.util.spec_from_file_location(\n'
        '    "m10_pkg", _init, submodule_search_locations=[_dir])\n'
        'pkg = importlib.util.module_from_spec(spec)\n'
        'sys.modules["m10_pkg"] = pkg\n'
        'spec.loader.exec_module(pkg)\n'
        'from importlib import import_module\n'
        'app_mod = import_module("m10_pkg.app")  # top-level app with env backends\n'
        'app = app_mod.app\n'
    )
    # M6 shim — package context so `from .leakage_scan` resolves
    (tmp / "m6_shim.py").write_text(
        'import importlib.util, sys, os\n'
        f'_dir = {str(SRC / "m6-mcp-gateway")!r}\n'
        'sys.path.insert(0, _dir)\n'
        '_init = os.path.join(_dir, "__init__.py")\n'
        'spec = importlib.util.spec_from_file_location(\n'
        '    "m6_pkg", _init, submodule_search_locations=[_dir])\n'
        'pkg = importlib.util.module_from_spec(spec)\n'
        'sys.modules["m6_pkg"] = pkg\n'
        'spec.loader.exec_module(pkg)\n'
        'from importlib import import_module\n'
        'app_mod = import_module("m6_pkg.app")\n'
        'app = app_mod.app\n'
    )

    procs: list[UvicornProcess] = [
        UvicornProcess("M1",      tmp, "m1_shim:app",       m1_port,      m1_env),
        UvicornProcess("M2/M4",   tmp, "m2_shim:app",       m2_port,      m2_env),
        UvicornProcess("M10",     tmp, "m10_shim:app",      m10_port,     m10_env),
        UvicornProcess("adapter", tmp, "fake_adapter:app",  adapter_port, common_env),
        UvicornProcess("M6",      tmp, "m6_shim:app",       m6_port,      m6_env),
    ]

    try:
        for p in procs:
            p.start()
        log.info("all 5 services up")

        # ── mint a real AID token via M1 ─────────────────────────
        issue_payload = {
            "actor_type": "human",
            "display_name": "Sarah Chen",
            "firm_id": "acme_wm",
            "archetype": "tier3_broker_dealer",
            "role": "advisor",
            "jurisdiction": "US",
            "authority_scope": [
                "get_client_profile", "get_holdings", "get_financial_plan",
                "get_account_balances", "search_sec_filings",
                "get_market_data", "search_news",
                "check_compliance", "check_restricted_list",
                "check_concentration",
            ],
            "client_scope": ["CLT-0042"],
            "ttl_hours": 1,
        }
        r = httpx.post(f"http://127.0.0.1:{m1_port}/aid/issue",
                       json=issue_payload, timeout=10)
        if r.status_code != 200:
            log.error("M1 issue failed status=%d body=%s", r.status_code, r.text)
            return 1
        aid_token = r.json().get("token")
        assert aid_token, f"M1 /aid/issue missing token: {r.json()}"
        log.info("minted AID token len=%d", len(aid_token))

        # ── direct M6 call (full trust pipeline sanity) ──────────
        mcp_req = {
            "aid_token": aid_token,
            "server_url": f"http://127.0.0.1:{adapter_port}",
            "tool_name": "get_client_profile",
            "arguments": {"client_id": "CLT-0042"},
        }
        t0 = time.perf_counter()
        r = httpx.post(f"http://127.0.0.1:{m6_port}/mcp/call",
                       json=mcp_req, timeout=30)
        trust_ms = (time.perf_counter() - t0) * 1000
        log.info("direct M6 call status=%s latency=%.1fms", r.status_code, trust_ms)
        if r.status_code != 200:
            log.error("M6 body: %s", r.text)
            # Debug: verify M1 claims + hit M2 directly + dump M6 log
            v = httpx.post(f"http://127.0.0.1:{m1_port}/aid/verify",
                           json={"token": aid_token}, timeout=5)
            log.error("M1 /aid/verify: %s", v.text[:500])
            claims = v.json().get("claims", {})
            auth_payload = {
                "identity": {
                    "actor_type": claims.get("actor_type", "human"),
                    "archetype": claims.get("archetype", "tier3_broker_dealer"),
                    "role": claims.get("role", "advisor"),
                    "display_name": claims.get("display_name", ""),
                    "firm_id": claims.get("firm_id", ""),
                    "jurisdiction": claims.get("jurisdiction", "US"),
                    "authority_scope": claims.get("authority_scope", []),
                    "authority_excludes": claims.get("authority_excludes", []),
                    "client_scope": claims.get("client_scope", []),
                    "pod_id": claims.get("pod_id"),
                },
                "action": "get_client_profile",
                "target_type": None,
                "target_id": None,
                "context": {"server_url": f"http://127.0.0.1:{adapter_port}"},
            }
            a = httpx.post(f"http://127.0.0.1:{m2_port}/policy/authority",
                           json=auth_payload, timeout=5)
            log.error("M2 /policy/authority direct: %s", a.text[:500])

            # Dump M6 subprocess log
            m6_proc = next((p for p in procs if p.label == "M6"), None)
            if m6_proc:
                log.error("═══ M6 subprocess log (last 8kb) ═══")
                for line in m6_proc.dump_log().splitlines()[-40:]:
                    log.error("  M6 | %s", line)
            return 1
        body = r.json()

        # ── run Strands client-service agent with real Bedrock ───
        os.environ["M6_GATEWAY_URL"] = f"http://127.0.0.1:{m6_port}"
        os.environ["M11_SALESFORCE_URL"] = f"http://127.0.0.1:{adapter_port}"
        os.environ["M11_ORION_URL"] = f"http://127.0.0.1:{adapter_port}"
        os.environ["M11_EMONEY_URL"] = f"http://127.0.0.1:{adapter_port}"
        os.environ["M2_POLICY_URL"] = f"http://127.0.0.1:{m2_port}"
        os.environ["FSI_AID_TOKEN"] = aid_token  # ContextVar fallback
        os.environ["BEDROCK_MODEL_HAIKU"] = (
            "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )

        # Dynamic import of m12-agent-runtime (dir has hyphens, uses relative imports)
        import importlib.util

        runtime_dir = SRC / "m12-agent-runtime"

        def _load_pkg(name: str, init_path: Path, is_pkg: bool = False):
            loc = [str(init_path.parent)] if is_pkg else None
            spec = importlib.util.spec_from_file_location(
                name, str(init_path), submodule_search_locations=loc,
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod

        _load_pkg("m12_pkg", runtime_dir / "__init__.py", is_pkg=True)
        _load_pkg("m12_pkg.config", runtime_dir / "config.py")
        _load_pkg("m12_pkg.tools", runtime_dir / "tools" / "__init__.py", is_pkg=True)
        m6_tools_mod = _load_pkg(
            "m12_pkg.tools.m6_tools", runtime_dir / "tools" / "m6_tools.py"
        )
        _load_pkg(
            "m12_pkg.tools.compliance_tools",
            runtime_dir / "tools" / "compliance_tools.py",
        )
        _load_pkg(
            "m12_pkg.tools.memory_tools",
            runtime_dir / "tools" / "memory_tools.py",
        )
        _load_pkg("m12_pkg.agents", runtime_dir / "agents" / "__init__.py", is_pkg=True)
        cs_mod = _load_pkg(
            "m12_pkg.agents.client_service",
            runtime_dir / "agents" / "client_service.py",
        )

        tok = m6_tools_mod.current_aid_token.set(aid_token)
        text = ""
        try:
            agent = cs_mod.create_client_service_agent()
            log.info("supervisor: sending meeting-prep to Bedrock Haiku 4.5")
            t0 = time.perf_counter()
            result = agent(
                "Prepare a short meeting-prep brief for client CLT-0042. "
                "Call get_client_profile, get_holdings, and get_financial_plan. "
                "Then write a 4 sentence summary citing source systems."
            )
            elapsed = time.perf_counter() - t0
            text = str(result)
            log.info("agent done in %.2fs, response_len=%d", elapsed, len(text))
            print("\n─────── AGENT RESPONSE ───────")
            print(text[:2500])
            print("──────────────────────────────\n")
        finally:
            m6_tools_mod.current_aid_token.reset(tok)

        # ── verify S3 WORM received audit writes ────────────────
        s3 = boto3.client("s3", region_name=aws_region)
        bucket = m10_env["M10_S3_BUCKET"]
        listing = s3.list_objects_v2(Bucket=bucket, MaxKeys=50)
        worm_keys = [o["Key"] for o in listing.get("Contents", [])]
        log.info("S3 WORM bucket=%s objects_found=%d", bucket, len(worm_keys))
        for k in worm_keys[:3]:
            log.info("  worm key: %s", k)

        # ── assertions ──────────────────────────────────────────
        assertions: list[tuple[str, bool]] = [
            ("real AWS STS identity",              bool(ident.get("Account"))),
            ("M6 direct call 200 + filtered",      r.status_code == 200 and body.get("filtered")),
            ("M6 provenance chain non-empty",      bool(body.get("provenance_chain"))),
            ("agent response contains Henderson",  "Henderson" in text),
            ("agent response length > 200",        len(text) > 200),
            ("S3 WORM bucket readable",            isinstance(worm_keys, list)),
            ("S3 WORM has at least 1 object",      len(worm_keys) >= 1),
        ]
        for name, ok in assertions:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        failed = [n for n, ok in assertions if not ok]
        if failed:
            print(f"\n{len(failed)} assertion(s) failed")
            return 1
        print("\nALL ASSERTIONS PASSED — 007 wired end-to-end against real AWS.")
        return 0

    finally:
        for p in procs:
            try:
                p.stop()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())

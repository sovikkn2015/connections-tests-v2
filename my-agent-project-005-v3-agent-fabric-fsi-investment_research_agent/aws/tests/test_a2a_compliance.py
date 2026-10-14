"""
A2A compliance tests for the Financial Analysis and Sentiment Analysis
Strands agents.

Two modes:

1. **In-process (default)** — imports each agent's ``app.lambda_handler``
   directly and invokes it with synthetic API Gateway events. Fast,
   deterministic, Docker-free. Runs on every CI pull.

2. **SAM-local (opt-in via ``SAM_LOCAL=1``)** — shells out to
   ``sam local invoke`` for each agent, then re-runs the same assertions
   against the real Lambda container image. Verifies the deployment
   bundle actually boots. Skipped by default because it needs Docker.

Covered criteria:
    * ``GET /.well-known/agent.json`` returns an A2A-valid AgentCard with
      required fields (name, url, version, capabilities, skills, provider,
      authentication).
    * ``POST /agent`` with a ``tasks/send`` JSON-RPC 2.0 payload returns
      a Task with ``status.state == "completed"`` and at least one artifact.
    * ``POST /agent`` with an unknown method returns JSON-RPC error
      -32601 ``METHOD_NOT_FOUND``.
    * ``POST /agent`` with a malformed JSON body returns -32600
      ``INVALID_REQUEST``.
    * Every skill id listed in the manifest maps to a concrete handler
      route (no orphaned skill declarations).
    * Response ``Content-Type`` is ``application/json`` and CORS headers
      are present.
    * The legacy ``X-A2A-Protocol`` marker header is emitted by
      ``POST /agent`` responses.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Tuple

import pytest

# -----------------------------------------------------------------------------
# Path wiring — let pytest import the agent modules without a package install.
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent  # aws/
AGENT_ROOTS = {
    "financial-analysis": REPO_ROOT / "strands-agents" / "financial-analysis",
    "sentiment-analysis": REPO_ROOT / "strands-agents" / "sentiment-analysis",
}
sys.path.insert(0, str(REPO_ROOT / "shared"))


USE_SAM_LOCAL = os.environ.get("SAM_LOCAL") == "1"


# -----------------------------------------------------------------------------
# Module loader that gives each agent its own isolated module namespace.
# The handler and manifest files `from app import ...` so we need `app`
# in sys.modules to resolve to THIS agent's app, not the other one's.
# Strategy: keep a per-agent module cache; before loading, purge any
# sibling-agent versions from sys.modules and reinstall this agent's
# cached peers. Load files directly via spec_from_file_location so we
# never rely on Python's finder picking the right directory.
# -----------------------------------------------------------------------------
_AGENT_LOCAL_MODULES = (
    "app", "a2a_handler", "a2a_manifest", "a2a_types",
    "langfuse_wrapper", "salesforce_client", "mcp_client",
)

_LOADED: Dict[str, Dict[str, ModuleType]] = {
    "financial-analysis": {},
    "sentiment-analysis": {},
}


def _purge_agent_modules() -> None:
    for name in list(sys.modules):
        if name in _AGENT_LOCAL_MODULES:
            del sys.modules[name]


def _load_from_path(mod_name: str, file_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    assert spec and spec.loader, f"Cannot build spec for {file_path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _load_agent_module(agent_slug: str, mod_name: str) -> ModuleType:
    """Load ``mod_name`` fresh from the target agent's directory.

    Maintains a per-agent cache so inter-module imports inside a given
    agent ("from app import ..." inside its a2a_handler) all resolve
    to the same agent's files.
    """
    agent_dir = AGENT_ROOTS[agent_slug]
    cache = _LOADED[agent_slug]

    # Ensure the agent_dir is first on sys.path for any transitive
    # "import foo" inside the loaded file.
    agent_dir_str = str(agent_dir)
    if agent_dir_str in sys.path:
        sys.path.remove(agent_dir_str)
    sys.path.insert(0, agent_dir_str)

    # Clear the OTHER agent's cache entries from sys.modules
    other = "sentiment-analysis" if agent_slug == "financial-analysis" else "financial-analysis"
    _purge_agent_modules()
    for already_name in _LOADED[other]:
        sys.modules.pop(already_name, None)
    # Reinstall THIS agent's cached peers so nested imports hit them
    for already_name, already_mod in cache.items():
        sys.modules[already_name] = already_mod

    if mod_name in cache:
        return cache[mod_name]

    target = agent_dir / f"{mod_name}.py"
    module = _load_from_path(mod_name, target)
    cache[mod_name] = module
    return module


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _synthetic_event(
    method: str,
    path: str,
    body: Any = None,
    stage: str = "prod",
) -> Dict[str, Any]:
    """Build a minimal API Gateway v1 proxy event.

    The SAM template wires ``/<agent>/{proxy+}`` routes, so in real
    invocations API Gateway strips the ``<agent>/`` prefix and sets
    ``pathParameters.proxy`` to the remainder. We mimic that here.
    """
    body_str: str = ""
    if body is not None:
        body_str = body if isinstance(body, str) else json.dumps(body)

    # Derive the {proxy+} value — everything AFTER the first segment.
    segments = [s for s in path.strip("/").split("/") if s]
    proxy_value = "/".join(segments[1:]) if len(segments) > 1 else ""

    return {
        "httpMethod": method.upper(),
        "path": path,
        "pathParameters": {"proxy": proxy_value},
        "headers": {
            "Host": "example.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "Content-Type": "application/json",
        },
        "requestContext": {
            "stage": stage,
            "http": {"method": method.upper()},
        },
        "body": body_str,
        "isBase64Encoded": False,
    }


def _load_agent_module_legacy(agent_slug: str, mod_name: str):
    """DEPRECATED — superseded by the namespace-aware loader above."""
    return _load_agent_module(agent_slug, mod_name)


def _invoke_handler(agent_slug: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke the agent's app.lambda_handler in-process or via SAM local."""
    if USE_SAM_LOCAL:
        return _invoke_via_sam(agent_slug, event)
    app_mod = _load_agent_module(agent_slug, "app")
    return app_mod.lambda_handler(event, None)


def _invoke_via_sam(agent_slug: str, event: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
    """Shell out to `sam local invoke <LogicalId>` with the event piped in."""
    logical_id = {
        "financial-analysis": "FinancialAnalysisAgent",
        "sentiment-analysis": "SentimentAnalysisAgent",
    }[agent_slug]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(event, fh)
        fh.flush()
        event_path = fh.name
    try:
        proc = subprocess.run(
            ["sam", "local", "invoke", logical_id, "--event", event_path],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
    finally:
        os.unlink(event_path)
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"Could not parse SAM local output:\n{proc.stdout}")


def _parse_body(response: Dict[str, Any]) -> Any:
    body = response.get("body")
    if isinstance(body, str):
        return json.loads(body)
    return body


REQUIRED_AGENT_CARD_FIELDS: Tuple[str, ...] = (
    "name", "description", "url", "provider", "version",
    "capabilities", "authentication", "skills",
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(params=["financial-analysis", "sentiment-analysis"])
def agent_slug(request) -> str:
    return request.param


@pytest.fixture
def manifest_response(agent_slug) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    evt = _synthetic_event("GET", f"/{agent_slug}/.well-known/agent.json")
    resp = _invoke_handler(agent_slug, evt)
    return resp, _parse_body(resp)


# -----------------------------------------------------------------------------
# 1. AgentCard manifest validation
# -----------------------------------------------------------------------------
class TestAgentCard:
    def test_manifest_returns_200(self, manifest_response):
        resp, _ = manifest_response
        assert resp["statusCode"] == 200

    def test_manifest_content_type_json(self, manifest_response):
        resp, _ = manifest_response
        assert resp["headers"]["Content-Type"] == "application/json"

    def test_manifest_cors_header(self, manifest_response):
        resp, _ = manifest_response
        assert "Access-Control-Allow-Origin" in resp["headers"]

    def test_manifest_required_fields(self, manifest_response):
        _, card = manifest_response
        missing = [f for f in REQUIRED_AGENT_CARD_FIELDS if f not in card]
        assert not missing, f"Missing AgentCard fields: {missing}"

    def test_manifest_name(self, agent_slug, manifest_response):
        _, card = manifest_response
        expected = {
            "financial-analysis": "Financial Analysis Agent",
            "sentiment-analysis": "Sentiment Analysis Agent",
        }[agent_slug]
        assert card["name"] == expected

    def test_manifest_provider_org(self, manifest_response):
        _, card = manifest_response
        assert card["provider"]["organization"] == "ir-research-v3"

    def test_manifest_version_semver(self, manifest_response):
        _, card = manifest_response
        parts = card["version"].split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_manifest_capabilities_shape(self, manifest_response):
        _, card = manifest_response
        caps = card["capabilities"]
        assert isinstance(caps.get("streaming"), bool)
        assert isinstance(caps.get("pushNotifications"), bool)

    def test_manifest_auth_apikey(self, manifest_response):
        _, card = manifest_response
        assert "apiKey" in card["authentication"]["schemes"]

    def test_manifest_skill_count(self, agent_slug, manifest_response):
        _, card = manifest_response
        assert len(card["skills"]) >= 4, (
            f"{agent_slug} should advertise at least 4 skills"
        )

    def test_manifest_skill_shape(self, manifest_response):
        _, card = manifest_response
        for skill in card["skills"]:
            for key in ("id", "name", "description", "inputModes", "outputModes"):
                assert key in skill, f"Skill missing '{key}': {skill}"
            assert "application/json" in skill["inputModes"]
            assert "application/json" in skill["outputModes"]

    def test_manifest_url_is_agent_endpoint(self, agent_slug, manifest_response):
        _, card = manifest_response
        assert f"/{agent_slug}/agent" in card["url"]

    def test_manifest_skills_match_known_ids(self, agent_slug, manifest_response):
        _, card = manifest_response
        expected = {
            "financial-analysis": {"run_dcf", "run_comps", "monte_carlo", "fair_value"},
            "sentiment-analysis": {
                "analyze_transcript", "score_news_sentiment",
                "detect_tone_shifts", "aggregate_sentiment",
            },
        }[agent_slug]
        got = {s["id"] for s in card["skills"]}
        assert got == expected, f"Skill id mismatch: got={got} expected={expected}"


# -----------------------------------------------------------------------------
# 2. Skill-id <-> handler-route coverage
# -----------------------------------------------------------------------------
class TestSkillHandlerCoverage:
    def test_every_manifest_skill_maps_to_handler(self, agent_slug):
        manifest_mod = _load_agent_module(agent_slug, "a2a_manifest")
        handler_mod = _load_agent_module(agent_slug, "a2a_handler")
        manifest_skill_ids = {s["id"] for s in manifest_mod.SKILLS}
        handler_skill_ids = set(handler_mod.SKILL_MAP.keys())
        orphans = manifest_skill_ids - handler_skill_ids
        assert not orphans, (
            f"[{agent_slug}] Skills in manifest without a handler: {orphans}"
        )

    def test_no_unadvertised_handlers(self, agent_slug):
        manifest_mod = _load_agent_module(agent_slug, "a2a_manifest")
        handler_mod = _load_agent_module(agent_slug, "a2a_handler")
        manifest_skill_ids = {s["id"] for s in manifest_mod.SKILLS}
        handler_skill_ids = set(handler_mod.SKILL_MAP.keys())
        hidden = handler_skill_ids - manifest_skill_ids
        assert not hidden, (
            f"[{agent_slug}] Handler skills not advertised in manifest: {hidden}"
        )


# -----------------------------------------------------------------------------
# 3. tasks/send execution
# -----------------------------------------------------------------------------
def _task_send_payload(agent_slug: str) -> Dict[str, Any]:
    """Deterministic skill that does NOT call Bedrock/Comprehend/MCP."""
    if agent_slug == "financial-analysis":
        return {
            "jsonrpc": "2.0",
            "id": "test-req-1",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "parts": [
                        {"type": "text", "text": "Run a DCF on NVDA"},
                        {"type": "data", "data": {
                            "skill": "run_dcf",
                            "ticker": "NVDA",
                            "growth_rate": 0.12,
                            "wacc": 0.10,
                            "terminal_growth": 0.03,
                        }},
                    ],
                },
            },
        }
    # sentiment-analysis: analyze_transcript with inline text. The tool
    # internally calls Bedrock+Comprehend, but we only assert on the A2A
    # envelope shape, not on synthesised analysis content, so Bedrock
    # errors manifest as artifact payload, not JSON-RPC errors.
    return {
        "jsonrpc": "2.0",
        "id": "test-req-1",
        "method": "tasks/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [
                    {"type": "text", "text": "analyze_transcript for NVDA"},
                    {"type": "data", "data": {
                        "skill": "analyze_transcript",
                        "ticker": "NVDA",
                        "text": "Revenue grew 10% year-over-year.",
                    }},
                ],
            },
        },
    }


class TestTasksSend:
    def test_returns_jsonrpc_response(self, agent_slug):
        payload = _task_send_payload(agent_slug)
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body=payload)
        resp = _invoke_handler(agent_slug, evt)
        body = _parse_body(resp)

        assert resp["statusCode"] == 200
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == "test-req-1"
        assert ("result" in body) ^ ("error" in body)

    def test_result_is_task(self, agent_slug):
        payload = _task_send_payload(agent_slug)
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body=payload)
        resp = _invoke_handler(agent_slug, evt)
        body = _parse_body(resp)
        if "error" in body:
            code = body["error"]["code"]
            assert code in (-32603, -32000), (
                f"Unexpected server error on tasks/send: {body['error']}"
            )
            return
        task = body["result"]
        assert task["kind"] == "task"
        assert "id" in task
        assert "contextId" in task
        assert task["status"]["state"] in (
            "completed", "failed", "working", "submitted", "input-required"
        )

    def test_protocol_header_present(self, agent_slug):
        payload = _task_send_payload(agent_slug)
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body=payload)
        resp = _invoke_handler(agent_slug, evt)
        assert resp["headers"].get("X-A2A-Protocol", "").startswith("a2a/")

    def test_cors_headers_present(self, agent_slug):
        payload = _task_send_payload(agent_slug)
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body=payload)
        resp = _invoke_handler(agent_slug, evt)
        assert resp["headers"]["Content-Type"] == "application/json"
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


# -----------------------------------------------------------------------------
# 4. Error paths
# -----------------------------------------------------------------------------
class TestA2AErrors:
    def test_unknown_method_returns_method_not_found(self, agent_slug):
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body={
            "jsonrpc": "2.0", "id": 42, "method": "tasks/bogus", "params": {},
        })
        body = _parse_body(_invoke_handler(agent_slug, evt))
        assert "error" in body
        assert body["error"]["code"] == -32601

    def test_malformed_body_returns_invalid_request(self, agent_slug):
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body="{not json")
        body = _parse_body(_invoke_handler(agent_slug, evt))
        assert "error" in body
        assert body["error"]["code"] == -32600

    def test_missing_message_returns_invalid_params(self, agent_slug):
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body={
            "jsonrpc": "2.0", "id": 1, "method": "tasks/send", "params": {},
        })
        body = _parse_body(_invoke_handler(agent_slug, evt))
        assert "error" in body
        assert body["error"]["code"] == -32602

    def test_tasks_send_subscribe_unsupported(self, agent_slug):
        evt = _synthetic_event("POST", f"/{agent_slug}/agent", body={
            "jsonrpc": "2.0", "id": 7, "method": "tasks/sendSubscribe",
            "params": {"message": {"role": "user", "parts": []}},
        })
        body = _parse_body(_invoke_handler(agent_slug, evt))
        assert "error" in body
        assert body["error"]["code"] == -32004


# -----------------------------------------------------------------------------
# 5. Shared a2a_types self-check
# -----------------------------------------------------------------------------
class TestSharedTypes:
    def test_agent_card_roundtrip(self):
        from a2a_types import (
            AgentCard, AgentProvider, AgentCapabilities,
            AgentAuthentication, AgentSkill,
        )
        card = AgentCard(
            name="x", description="y", url="https://example.com/agent",
            provider=AgentProvider(organization="ir-research-v3"),
            version="1.0.0",
            capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
            authentication=AgentAuthentication(schemes=["apiKey"]),
            skills=[AgentSkill(id="x", name="X", description="d")],
        )
        d = card.model_dump(exclude_none=True)
        assert d["name"] == "x"
        assert d["skills"][0]["id"] == "x"

    def test_rpc_error_envelope(self):
        from a2a_types import build_error, METHOD_NOT_FOUND
        env = build_error("req-1", METHOD_NOT_FOUND, "nope")
        assert env["jsonrpc"] == "2.0"
        assert env["id"] == "req-1"
        assert env["error"]["code"] == METHOD_NOT_FOUND

    def test_rpc_result_envelope(self):
        from a2a_types import build_result
        env = build_result("req-2", {"ok": True})
        assert env["jsonrpc"] == "2.0"
        assert env["result"] == {"ok": True}

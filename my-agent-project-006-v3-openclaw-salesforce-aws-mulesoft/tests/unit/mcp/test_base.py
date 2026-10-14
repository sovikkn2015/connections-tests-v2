"""Tests for the shared MCP base framework."""

from __future__ import annotations

import json

from _base import McpError, McpServer, McpValidationError, ToolSpec


def _make_server() -> McpServer:
    srv = McpServer(name="test", version="1.0.0", description="test")

    def echo(args, ctx):
        return {"echo": args.get("msg", ""), "principal": ctx.get("principal_id", "")}

    def validation_fail(args, ctx):
        raise McpValidationError("bad input")

    def boom(args, ctx):
        raise RuntimeError("kaboom")

    srv.register(
        ToolSpec(
            name="echo",
            description="echo",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        ),
        echo,
    )
    srv.register(ToolSpec(name="validation_fail", description="x"), validation_fail)
    srv.register(ToolSpec(name="boom", description="x"), boom)
    return srv


def _event(method="POST", path="/tools/call", body=None, headers=None):
    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body is not None else None,
        "headers": headers or {},
    }


def test_get_returns_info():
    resp = _make_server().handle(_event(method="GET", path="/"))
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["name"] == "test"
    assert "echo" in body["tools"]


def test_tools_list():
    resp = _make_server().handle(_event(path="/tools/list", body={}))
    body = json.loads(resp["body"])
    assert {t["name"] for t in body["tools"]} == {"echo", "validation_fail", "boom"}


def test_tools_call_ok_echoes_args_and_principal():
    resp = _make_server().handle(
        _event(
            path="/tools/call",
            body={"name": "echo", "arguments": {"msg": "hi"}, "tool_call_id": "tc_001"},
            headers={"X-Principal-Id": "sarah@firm.com"},
        )
    )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["status"] == "ok"
    assert body["result"] == {"echo": "hi", "principal": "sarah@firm.com"}
    assert body["tool_call_id"] == "tc_001"


def test_tools_call_unknown_tool_returns_404():
    resp = _make_server().handle(_event(path="/tools/call", body={"name": "nope"}))
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 404
    assert body["status"] == "error"
    assert body["error"]["code"] == -32601


def test_tools_call_validation_error_surfaces():
    resp = _make_server().handle(_event(path="/tools/call", body={"name": "validation_fail"}))
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 400
    assert body["error"]["code"] == -32602


def test_tools_call_unhandled_exception_returns_500():
    resp = _make_server().handle(_event(path="/tools/call", body={"name": "boom"}))
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 500
    assert body["status"] == "error"


def test_options_preflight():
    resp = _make_server().handle(_event(method="OPTIONS"))
    assert resp["statusCode"] == 200


def test_api_key_enforced_when_env_set(monkeypatch):
    srv = _make_server()
    monkeypatch.setenv("MCP_API_KEY", "secret-xyz")
    resp = srv.handle(_event(path="/tools/call", body={"name": "echo"}))
    assert resp["statusCode"] == 401
    resp = srv.handle(
        _event(
            path="/tools/call",
            body={"name": "echo", "arguments": {"msg": "ok"}},
            headers={"X-MCP-API-Key": "secret-xyz"},
        )
    )
    assert resp["statusCode"] == 200


def test_malformed_json_body():
    resp = _make_server().handle({
        "httpMethod": "POST",
        "path": "/tools/call",
        "body": "{not json",
        "headers": {},
    })
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 400
    assert body["error"]["code"] == -32602


def test_mcp_error_subclasses_have_distinct_codes():
    assert McpError("x").code == -32000
    assert McpValidationError("x").code == -32602

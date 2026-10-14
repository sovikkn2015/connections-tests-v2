#!/usr/bin/env node
/**
 * MCP REST Bridge — translates MCP stdio JSON-RPC to Lambda REST endpoints.
 *
 * Usage: MCP_BASE_URL=https://...  MCP_API_KEY=...  node mcp-rest-bridge.mjs
 *
 * The Lambda MCP servers expose:
 *   GET  /           → server info
 *   POST /tools/list → tool catalog
 *   POST /tools/call → invoke tool {name, arguments}
 *
 * This bridge speaks MCP stdio (JSON-RPC over stdin/stdout) so OpenClaw
 * can connect via transport:"stdio".
 */

import { createInterface } from "node:readline";

const BASE_URL = process.env.MCP_BASE_URL;
const API_KEY = process.env.MCP_API_KEY;

if (!BASE_URL || !API_KEY) {
  process.stderr.write("MCP_BASE_URL and MCP_API_KEY are required\n");
  process.exit(1);
}

const SERVER_NAME = BASE_URL.split("/").pop() || "mcp-rest-bridge";

function send(msg) {
  const json = JSON.stringify(msg);
  process.stdout.write(json + "\n");
}

async function restPost(path, body = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`REST ${path} failed (${res.status}): ${text}`);
  }
  return res.json();
}

async function handleRequest(req) {
  const { id, method, params } = req;

  switch (method) {
    case "initialize":
      return {
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: SERVER_NAME, version: "1.0.0" },
        },
      };

    case "notifications/initialized":
      // No response needed for notifications
      return null;

    case "tools/list": {
      const data = await restPost("/tools/list", {});
      return {
        jsonrpc: "2.0",
        id,
        result: { tools: data.tools || [] },
      };
    }

    case "tools/call": {
      const { name, arguments: args } = params || {};
      const data = await restPost("/tools/call", { name, arguments: args });
      // Normalize response to MCP format
      const content = data.content || [{ type: "text", text: JSON.stringify(data.result ?? data) }];
      return {
        jsonrpc: "2.0",
        id,
        result: { content, isError: data.isError || false },
      };
    }

    case "ping":
      return { jsonrpc: "2.0", id, result: {} };

    default:
      return {
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `Method not found: ${method}` },
      };
  }
}

// Track pending async work so we don't exit before responses are sent
const pending = new Set();

const rl = createInterface({ input: process.stdin, terminal: false });
let stdinClosed = false;

rl.on("line", (line) => {
  if (!line.trim()) return;
  const p = (async () => {
    try {
      const req = JSON.parse(line);
      const response = await handleRequest(req);
      if (response) send(response);
    } catch (err) {
      process.stderr.write(`Bridge error: ${err.message}\n`);
      try {
        const req = JSON.parse(line);
        if (req.id != null) {
          send({
            jsonrpc: "2.0",
            id: req.id,
            error: { code: -32603, message: err.message },
          });
        }
      } catch (_) {}
    }
  })();
  pending.add(p);
  p.finally(() => {
    pending.delete(p);
    if (stdinClosed && pending.size === 0) process.exit(0);
  });
});

rl.on("close", () => {
  stdinClosed = true;
  if (pending.size === 0) process.exit(0);
});

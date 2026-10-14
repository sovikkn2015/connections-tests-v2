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
 *
 * Resilience (added 2026-04-21):
 *   - 3 attempts with exponential backoff (500ms, 1500ms, 3500ms)
 *   - 15s per-attempt timeout
 *   - Retry on: 429, 5xx, AbortError (timeout), fetch errors
 *   - NO retry on: 400, 401, 403, 404 (permanent failures)
 */

import { createInterface } from "node:readline";

const GATEWAY_URL = process.env.MCP_GATEWAY_URL;
const SERVER_PATH = process.env.MCP_SERVER_PATH;
const API_KEY = process.env.MCP_API_KEY;
const MAX_ATTEMPTS = parseInt(process.env.MCP_MAX_ATTEMPTS || "3", 10);
const ATTEMPT_TIMEOUT_MS = parseInt(process.env.MCP_ATTEMPT_TIMEOUT_MS || "15000", 10);

// Legacy: MCP_BASE_URL was used when OpenClaw substituted ${} at config load.
// Current path: gateway URL + server path are separate so OpenClaw inherits
// MCP_GATEWAY_URL and MCP_API_KEY via parent env, and only MCP_SERVER_PATH
// comes from the openclaw.json mcp.servers.*.env block.
const BASE_URL = process.env.MCP_BASE_URL
  || (GATEWAY_URL && SERVER_PATH ? `${GATEWAY_URL.replace(/\/$/, "")}/${SERVER_PATH}` : null);

if (!BASE_URL || !API_KEY) {
  process.stderr.write(
    `[mcp-bridge] startup failed: BASE_URL=${BASE_URL ? "set" : "missing"}, ` +
    `API_KEY=${API_KEY ? "set" : "missing"}, ` +
    `MCP_GATEWAY_URL=${process.env.MCP_GATEWAY_URL ? "set" : "missing"}, ` +
    `MCP_SERVER_PATH=${process.env.MCP_SERVER_PATH || "missing"}\n`,
  );
  process.exit(1);
}

const SERVER_NAME = BASE_URL.split("/").pop() || "mcp-rest-bridge";

function send(msg) {
  const json = JSON.stringify(msg);
  process.stdout.write(json + "\n");
}

function isRetryable(status, err) {
  if (err && (err.name === "AbortError" || err.name === "TypeError")) return true;
  if (status === 429) return true;
  if (status >= 500 && status <= 599) return true;
  return false;
}

async function restPostWithRetry(path, body = {}) {
  let lastErr = null;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ATTEMPT_TIMEOUT_MS);
    try {
      const res = await fetch(`${BASE_URL}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": API_KEY,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (res.ok) {
        return await res.json();
      }

      const text = await res.text().catch(() => "");
      const snippet = text.slice(0, 500);

      if (!isRetryable(res.status, null) || attempt === MAX_ATTEMPTS) {
        throw new Error(`REST ${path} failed (${res.status}): ${snippet}`);
      }
      process.stderr.write(
        `[mcp-bridge ${SERVER_NAME}] attempt ${attempt}/${MAX_ATTEMPTS} failed (${res.status}), retrying\n`,
      );
    } catch (err) {
      clearTimeout(timer);
      lastErr = err;
      if (!isRetryable(null, err) || attempt === MAX_ATTEMPTS) {
        throw err;
      }
      process.stderr.write(
        `[mcp-bridge ${SERVER_NAME}] attempt ${attempt}/${MAX_ATTEMPTS} error: ${err.message}, retrying\n`,
      );
    }

    // Exponential backoff: 500ms, 1500ms, 3500ms
    const backoff = 500 * (2 ** (attempt - 1));
    await new Promise(r => setTimeout(r, backoff));
  }

  throw lastErr || new Error(`REST ${path} failed after ${MAX_ATTEMPTS} attempts`);
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
          serverInfo: { name: SERVER_NAME, version: "1.1.0" },
        },
      };

    case "notifications/initialized":
      return null;

    case "tools/list": {
      const data = await restPostWithRetry("/tools/list", {});
      return {
        jsonrpc: "2.0",
        id,
        result: { tools: data.tools || [] },
      };
    }

    case "tools/call": {
      const { name, arguments: args } = params || {};
      const data = await restPostWithRetry("/tools/call", { name, arguments: args });
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

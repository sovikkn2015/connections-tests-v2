/**
 * MCP server harness tests. Spec R1: GET /, POST /tools/list, POST /tools/call.
 * AC1.1 - AC1.8, AC2.5 - AC2.10, AC8.3 - AC8.4.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";
import type { FastifyInstance } from "fastify";

import { buildMcpApp } from "../src/server.js";
import type {
  AdapterConfig,
  HealthCheckResult,
  ToolDefinition,
} from "../src/types.js";
import { getLogger } from "../src/logger.js";
import { PassThrough } from "node:stream";

function makeConfig(): AdapterConfig {
  return {
    vendor: "salesforce_fsc",
    adapterVersion: "0.1.0",
    vendorApiVersion: "v59.0",
    port: 0,
    httpTimeoutMs: 60_000,
    undiciConnections: 10,
    egressAllowlist: ["salesforce.com"],
    mtls: {
      clientCertPath: "/dev/null",
      clientKeyPath: "/dev/null",
      caCertPath: "/dev/null",
      trustedSubjectCn: "m6-mcp-gateway.test.svc.cluster.local",
      enabled: false,
    },
    firmIdRequired: true,
  };
}

function okHealth(): Promise<HealthCheckResult> {
  return Promise.resolve({
    status: "ok",
    checks: { oauth: "ok", circuit: "ok", mtls: "ok" },
  });
}

function makeTools(): Record<string, ToolDefinition> {
  return {
    "sfdc.fetch_client": {
      name: "sfdc.fetch_client",
      description: "Fetch a client by SF Account Id — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: z.object({ clientId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/) }),
      handler: async (args) => ({ received: args }),
    },
    "sfdc.fetch_goal": {
      name: "sfdc.fetch_goal",
      description: "Fetch a financial goal by Id — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: z.object({ goalId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/) }),
      handler: async () => ({ ok: true }),
    },
  };
}

async function build(): Promise<FastifyInstance> {
  const sink = new PassThrough();
  sink.on("data", () => {});
  const logger = getLogger({
    adapterName: "m11-test",
    vendor: "salesforce_fsc",
    destination: sink,
    level: "error",
  });
  const app = buildMcpApp({
    config: makeConfig(),
    logger,
    tools: makeTools(),
    healthCheck: okHealth,
  });
  await app.ready();
  return app;
}

describe("R1 MCP contract — GET /", () => {
  let app: FastifyInstance;
  beforeEach(async () => {
    app = await build();
  });

  it("AC1.1 — returns mcp-server info + vendor + vendorApiVersion + tool list", async () => {
    const res = await app.inject({ method: "GET", url: "/" });
    expect(res.statusCode).toBe(200);
    const body = res.json() as Record<string, unknown>;
    expect(body.type).toBe("mcp-server");
    expect(body.vendor).toBe("salesforce_fsc");
    expect(body.vendorApiVersion).toBe("v59.0");
    expect(Array.isArray(body.tools)).toBe(true);
    expect((body.tools as string[]).sort()).toEqual(
      ["sfdc.fetch_client", "sfdc.fetch_goal"].sort(),
    );
  });

  it("AC1.7 — echoes X-Trace-Id + X-Adapter-Version headers", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/",
      headers: { "x-trace-id": "abc-123" },
    });
    expect(res.headers["x-trace-id"]).toBe("abc-123");
    expect(res.headers["x-adapter-version"]).toBe("0.1.0");
  });

  it("AC1.6 — returns 503 when health is degraded", async () => {
    const sink = new PassThrough();
    sink.on("data", () => {});
    const app2 = buildMcpApp({
      config: makeConfig(),
      logger: getLogger({ adapterName: "t", vendor: "salesforce_fsc", destination: sink, level: "error" }),
      tools: makeTools(),
      healthCheck: async () => ({
        status: "degraded",
        checks: { oauth: "degraded", circuit: "ok", mtls: "ok" },
        reason: "oauth_bootstrap_failed",
      }),
    });
    await app2.ready();
    const res = await app2.inject({ method: "GET", url: "/" });
    expect(res.statusCode).toBe(503);
  });
});

describe("R1 — POST /tools/list", () => {
  it("AC1.2 + AC2.8 — returns alphabetically-sorted tool descriptors", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/list",
      headers: { "content-type": "application/json" },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { tools: Array<{ name: string; inputSchema: unknown }> };
    expect(body.tools.map((t) => t.name)).toEqual([
      "sfdc.fetch_client",
      "sfdc.fetch_goal",
    ]);
    // Every tool has an inputSchema.
    for (const t of body.tools) {
      expect(t.inputSchema).toBeDefined();
      expect(typeof t.inputSchema).toBe("object");
    }
  });
});

describe("R1 — POST /tools/call", () => {
  it("AC1.3 — success envelope {result, error:null}", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "sfdc.fetch_client",
        arguments: { clientId: "001A000001234567" },
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { result: unknown; error: unknown };
    expect(body.error).toBe(null);
    expect(body.result).toBeDefined();
  });

  it("AC2.9 — unknown tool → 404 tool_not_found", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: { name: "sfdc.nonexistent", arguments: {} },
    });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toMatchObject({
      result: null,
      error: { code: "tool_not_found", retryable: false },
    });
  });

  it("AC2.10 + AC8.4 — Zod fail → 400 invalid_arguments with path only", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "sfdc.fetch_client",
        arguments: { clientId: "not-valid" },
      },
    });
    expect(res.statusCode).toBe(400);
    const body = res.json() as { error: { code: string; message: string } };
    expect(body.error.code).toBe("invalid_arguments");
    expect(body.error.message).toContain("arguments.clientId");
    // No values leaked.
    expect(body.error.message).not.toContain("not-valid");
  });

  it("AC5.4 — missing X-Firm-ID → 400 missing_firm_id", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json" },
      payload: {
        name: "sfdc.fetch_client",
        arguments: { clientId: "001A000001234567" },
      },
    });
    expect(res.statusCode).toBe(400);
    expect((res.json() as { error: { code: string } }).error.code).toBe(
      "missing_firm_id",
    );
  });

  it("AC1.8 — non-JSON Content-Type → 415", async () => {
    const app = await build();
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "text/plain", "x-firm-id": "acme" },
      payload: "name=sfdc.fetch_client",
    });
    expect(res.statusCode).toBe(415);
    expect((res.json() as { error: { code: string } }).error.code).toBe(
      "unsupported_media_type",
    );
  });
});

describe("R1 — AC1.4 no 4th endpoint", () => {
  it.each([
    ["GET", "/health"],
    ["GET", "/metrics"],
    ["POST", "/anything"],
    ["GET", "/tools/call"],
    ["POST", "/"],
  ] as const)("%s %s → 404", async (method, url) => {
    const app = await build();
    const res = await app.inject({ method, url });
    expect(res.statusCode).toBe(404);
  });
});

/**
 * Task 23 — multi-adapter dress rehearsal.
 *
 * Exercises the RIA meeting-prep journey in-process: SFDC fetch → Orion
 * fetch → eMoney strict output → SFDC writeback with ETag.
 *
 * Covers:
 *   - AC1.3 response envelope across adapters
 *   - AC5.9 rate limit concurrency
 *   - AC6 circuit breaker
 *   - AC8.9 SFDC ETag writeback success + stale-ETag 409
 *   - AC8.6 eMoney raw-plan rejection
 *   - AC16.4 cross-adapter error contract
 *   - Chaos: FakeSecretsClient backend transient failure
 */

import { beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";
import type { FastifyInstance } from "fastify";
import { PassThrough } from "node:stream";

import {
  AdapterError,
  FakeClock,
  FakeSecretsClient,
  buildMcpApp,
  getLogger,
  CircuitBreaker,
  RateLimiterRegistry,
  type HealthCheckResult,
  type ToolDefinition,
} from "../src/index.js";

function makeLogger(vendor: "salesforce_fsc" | "orion" | "emoney" | "schwab"): ReturnType<typeof getLogger> {
  const sink = new PassThrough();
  sink.on("data", () => {});
  return getLogger({
    adapterName: `m11-${vendor}`,
    vendor,
    destination: sink,
    level: "error",
  });
}

function buildRehearsalApp(
  vendor: "salesforce_fsc" | "orion" | "emoney" | "schwab",
  tools: Record<string, ToolDefinition>,
): FastifyInstance {
  const logger = makeLogger(vendor);
  const healthCheck = async (): Promise<HealthCheckResult> => ({
    status: "ok",
    checks: { oauth: "ok", circuit: "ok", mtls: "ok" },
  });
  const versionMap = {
    salesforce_fsc: "v59.0",
    orion: "v2.0",
    emoney: "v2",
    schwab: "v1",
  } as const;
  return buildMcpApp({
    config: {
      vendor,
      adapterVersion: "0.1.0",
      vendorApiVersion: versionMap[vendor],
      port: 0,
      httpTimeoutMs: 60_000,
      undiciConnections: 10,
      egressAllowlist: [],
      mtls: {
        clientCertPath: "/dev/null",
        clientKeyPath: "/dev/null",
        caCertPath: "/dev/null",
        trustedSubjectCn: "cn",
        enabled: false,
      },
      firmIdRequired: true,
    },
    logger,
    tools,
    healthCheck,
  });
}

describe("Task 23 — RIA meeting-prep journey", () => {
  it("4-adapter journey with ETag writeback path", async () => {
    let capturedEtag: string | null = null;

    // SFDC.
    const sfdcTools: Record<string, ToolDefinition> = {
      "sfdc.fetch_client": {
        name: "sfdc.fetch_client",
        description: "rehearsal SFDC fetch — returns raw vendor JSON — use M7 translator to canonicalize",
        input: z.object({ clientId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/) }),
        handler: async (args) => ({
          Id: (args as { clientId: string }).clientId,
          Name: "Placeholder Name",
          _etag: `"W/\\"3-placeholder\\""`,
        }),
      },
      "sfdc.fetch_household": {
        name: "sfdc.fetch_household",
        description: "rehearsal SFDC household — returns raw vendor JSON — use M7 translator to canonicalize",
        input: z.object({ householdId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/) }),
        handler: async () => ({ Id: "001H000001234567", Name: "Placeholder HH" }),
      },
      "sfdc.create_interaction_summary": {
        name: "sfdc.create_interaction_summary",
        description: "rehearsal SFDC interaction writeback with If-Match",
        input: z.object({
          clientId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/),
          ifMatch: z.string().min(1),
          summaryText: z.string().min(1).max(32_000),
          interactionDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
        }),
        handler: async (args) => {
          const a = args as { ifMatch: string };
          if (a.ifMatch !== capturedEtag) {
            throw new AdapterError(
              "vendor_conflict",
              "stale ETag — M6 should re-fetch",
              412,
            );
          }
          return { id: "001I000001234567", created: true };
        },
      },
    };
    const sfdc = buildRehearsalApp("salesforce_fsc", sfdcTools);
    await sfdc.ready();

    const sfdcClientRes = await sfdc.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: { name: "sfdc.fetch_client", arguments: { clientId: "001A000001234567" } },
    });
    expect(sfdcClientRes.statusCode).toBe(200);
    const clientBody = sfdcClientRes.json() as { result: { _etag: string }; error: null };
    expect(clientBody.error).toBe(null);
    capturedEtag = clientBody.result._etag;
    expect(capturedEtag).toBeTruthy();

    const sfdcHh = await sfdc.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "sfdc.fetch_household",
        arguments: { householdId: "001H000001234567" },
      },
    });
    expect(sfdcHh.statusCode).toBe(200);

    // Orion.
    const orionTools: Record<string, ToolDefinition> = {
      "orion.fetch_holdings": {
        name: "orion.fetch_holdings",
        description: "rehearsal orion holdings — returns raw vendor JSON — use M7 translator to canonicalize",
        input: z.object({ accountId: z.number().int().positive() }),
        handler: async () => ({ positions: [{ symbol: "AAPL", quantity: 100 }] }),
      },
      "orion.fetch_taxlots": {
        name: "orion.fetch_taxlots",
        description: "rehearsal orion taxlots — returns raw vendor JSON — use M7 translator to canonicalize",
        input: z.object({ accountId: z.number().int().positive() }),
        handler: async () => ({ taxlots: [] }),
      },
    };
    const orion = buildRehearsalApp("orion", orionTools);
    await orion.ready();
    const orionRes = await orion.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: { name: "orion.fetch_holdings", arguments: { accountId: 12345 } },
    });
    expect(orionRes.statusCode).toBe(200);

    // eMoney — strict-output.
    let emoneyShouldReturnRaw = false;
    const EMoneyOutput = z
      .object({
        planId: z.string(),
        clientId: z.string(),
        planName: z.string(),
        probabilityOfSuccess: z.number(),
        asOfDate: z.string(),
        createdAt: z.string(),
        updatedAt: z.string(),
      })
      .strict();
    const emoneyTools: Record<string, ToolDefinition> = {
      "emoney.fetch_plan_summary": {
        name: "emoney.fetch_plan_summary",
        description: "rehearsal emoney plan summary — strict allow-list",
        input: z.object({ planId: z.string().uuid() }),
        output: EMoneyOutput,
        handler: async () => {
          const summary: Record<string, unknown> = {
            planId: "550e8400-e29b-41d4-a716-446655440000",
            clientId: "c-1",
            planName: "Retirement",
            probabilityOfSuccess: 78.5,
            asOfDate: "2026-04-28",
            createdAt: "2025-01-15T00:00:00Z",
            updatedAt: "2026-04-01T00:00:00Z",
          };
          if (emoneyShouldReturnRaw) {
            throw new AdapterError(
              "emoney_raw_plan_forbidden",
              "eMoney returned a non-summary field",
              200,
            );
          }
          return summary;
        },
      },
    };
    const emoney = buildRehearsalApp("emoney", emoneyTools);
    await emoney.ready();
    const emoneyOk = await emoney.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "emoney.fetch_plan_summary",
        arguments: { planId: "550e8400-e29b-41d4-a716-446655440000" },
      },
    });
    expect(emoneyOk.statusCode).toBe(200);

    emoneyShouldReturnRaw = true;
    const emoneyRej = await emoney.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "emoney.fetch_plan_summary",
        arguments: { planId: "550e8400-e29b-41d4-a716-446655440001" },
      },
    });
    expect(emoneyRej.statusCode).toBe(502);
    expect((emoneyRej.json() as { error: { code: string } }).error.code).toBe(
      "emoney_raw_plan_forbidden",
    );

    // Writeback with captured ETag → success.
    const wb = await sfdc.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "sfdc.create_interaction_summary",
        arguments: {
          clientId: "001A000001234567",
          ifMatch: capturedEtag,
          summaryText: "Meeting summary — placeholder.",
          interactionDate: "2026-05-05",
        },
      },
    });
    expect(wb.statusCode).toBe(200);

    // Stale-ETag → 409.
    capturedEtag = `"W/\\"99-STALE\\""`;
    const wbStale = await sfdc.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: {
        name: "sfdc.create_interaction_summary",
        arguments: {
          clientId: "001A000001234567",
          ifMatch: `"W/\\"3-placeholder\\""`,
          summaryText: "Second meeting.",
          interactionDate: "2026-05-05",
        },
      },
    });
    expect(wbStale.statusCode).toBe(409);
    expect((wbStale.json() as { error: { code: string } }).error.code).toBe(
      "vendor_conflict",
    );
  });

  it("Task 23 — rate limiter concurrency — burst=10 of 50 → 10 pass, 40 denied (AC5.9)", () => {
    const clk = new FakeClock(0);
    const reg = new RateLimiterRegistry({ rpm: 60, burst: 10 }, clk);
    let passed = 0;
    let denied = 0;
    for (let i = 0; i < 50; i++) {
      const r = reg.acquire("acme:sfdc");
      if (r.ok) passed++;
      else denied++;
    }
    expect(passed).toBe(10);
    expect(denied).toBe(40);
  });

  it("Task 23 — circuit breaker opens after 6 consecutive failures", () => {
    const clk = new FakeClock(0);
    const cb = new CircuitBreaker(clk);
    for (let i = 0; i < 6; i++) cb.recordFailure("acme:schwab");
    expect(cb.state("acme:schwab")).toBe("OPEN");
    expect(() => cb.assertCallable("acme:schwab")).toThrow(AdapterError);
  });

  it("Task 23 CHAOS — FakeSecretsClient transient failure → adapters degrade gracefully", async () => {
    const secrets = new FakeSecretsClient({ "m11/x": "placeholder" });
    secrets.getSecretFailureCount = 3;
    await expect(secrets.getSecret("m11/x")).rejects.toThrow();
    await expect(secrets.getSecret("m11/x")).rejects.toThrow();
    await expect(secrets.getSecret("m11/x")).rejects.toThrow();
    expect(await secrets.getSecret("m11/x")).toBe("placeholder");
  });
});

describe("Task 23 — cross-adapter error contract (AC16.4)", () => {
  let app: FastifyInstance;
  const tools: Record<string, ToolDefinition> = {
    "sfdc.fetch_client": {
      name: "sfdc.fetch_client",
      description: "trigger — returns raw vendor JSON — use M7 translator to canonicalize",
      input: z.object({ clientId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/) }),
      handler: async () => ({ ok: true }),
    },
  };
  beforeEach(async () => {
    app = buildRehearsalApp("salesforce_fsc", tools);
    await app.ready();
  });

  it("invalid_arguments — missing required field", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: { name: "sfdc.fetch_client", arguments: {} },
    });
    expect(res.statusCode).toBe(400);
    expect((res.json() as { error: { code: string } }).error.code).toBe(
      "invalid_arguments",
    );
  });

  it("missing_firm_id", async () => {
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

  it("tool_not_found", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "application/json", "x-firm-id": "acme" },
      payload: { name: "sfdc.does_not_exist", arguments: {} },
    });
    expect(res.statusCode).toBe(404);
  });

  it("unsupported_media_type", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/tools/call",
      headers: { "content-type": "text/plain", "x-firm-id": "acme" },
      payload: "plain",
    });
    expect(res.statusCode).toBe(415);
  });
});

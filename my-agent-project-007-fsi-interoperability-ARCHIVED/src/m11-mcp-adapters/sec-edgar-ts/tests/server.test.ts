/**
 * Tests for SEC EDGAR TypeScript MCP adapter.
 * Mirrors the Python test suite in sec-edgar/tests/test_sec_edgar.py.
 */

import { describe, it, expect, vi, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../src/server.js";

// ---------------------------------------------------------------------------
// Test 1: Health check / server info (GET /)
// ---------------------------------------------------------------------------
describe("GET /", () => {
  it("returns server info with healthy status", async () => {
    const res = await request(app).get("/");
    expect(res.status).toBe(200);
    expect(res.body.name).toBe("sec-edgar-ts-adapter");
    expect(res.body.version).toBe("1.0.0");
    expect(res.body.vendor).toBe("sec_edgar");
    expect(res.body.status).toBe("healthy");
    expect(res.body.capabilities.tools).toBe(true);
  });

  it("includes x-request-id header", async () => {
    const res = await request(app).get("/");
    expect(res.headers["x-request-id"]).toBeDefined();
  });

  it("includes x-rate-limit-remaining header", async () => {
    const res = await request(app).get("/");
    expect(res.headers["x-rate-limit-remaining"]).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Test 2: Tools list (POST /tools/list)
// ---------------------------------------------------------------------------
describe("POST /tools/list", () => {
  it("returns exactly 3 tools", async () => {
    const res = await request(app).post("/tools/list").send({});
    expect(res.status).toBe(200);
    const tools = res.body.tools;
    expect(tools).toHaveLength(3);
    const names = new Set(tools.map((t: { name: string }) => t.name));
    expect(names).toEqual(
      new Set(["search_filings", "get_filing", "get_company_facts"]),
    );
  });

  it("each tool has valid inputSchema", async () => {
    const res = await request(app).post("/tools/list").send({});
    for (const tool of res.body.tools) {
      expect(tool.inputSchema.type).toBe("object");
      expect(tool.inputSchema.properties).toBeDefined();
      expect(tool.inputSchema.required).toBeDefined();
    }
  });
});


// ---------------------------------------------------------------------------
// Test 3: Tool call — search_filings with mock
// ---------------------------------------------------------------------------
describe("POST /tools/call — search_filings", () => {
  it("returns results when fetch succeeds", async () => {
    const mockData = {
      hits: {
        hits: [{ _source: { file_num: "001-36743", form_type: "10-K" } }],
      },
      total: { value: 1 },
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await request(app)
      .post("/tools/call")
      .send({
        name: "search_filings",
        arguments: { query: "AAPL", filing_type: "10-K", limit: 5 },
      });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBeUndefined();
    expect(res.body.content).toBeDefined();
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.hits).toBeDefined();

    vi.restoreAllMocks();
  });

  it("returns INVALID_PARAMS when query missing", async () => {
    const res = await request(app)
      .post("/tools/call")
      .send({ name: "search_filings", arguments: {} });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBe(true);
    expect(res.body.errorCode).toBe("INVALID_PARAMS");
  });
});

// ---------------------------------------------------------------------------
// Test 4: Tool call — get_filing with mock
// ---------------------------------------------------------------------------
describe("POST /tools/call — get_filing", () => {
  it("returns filing metadata when fetch succeeds", async () => {
    const mockData = {
      cik: "320193",
      entityType: "operating",
      name: "Apple Inc.",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await request(app)
      .post("/tools/call")
      .send({
        name: "get_filing",
        arguments: { accession_number: "0000320193-23-000106" },
      });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBeUndefined();
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.name).toBe("Apple Inc.");

    vi.restoreAllMocks();
  });

  it("returns INVALID_PARAMS when accession_number missing", async () => {
    const res = await request(app)
      .post("/tools/call")
      .send({ name: "get_filing", arguments: {} });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBe(true);
    expect(res.body.errorCode).toBe("INVALID_PARAMS");
  });
});

// ---------------------------------------------------------------------------
// Test 5: Tool call — get_company_facts with mock
// ---------------------------------------------------------------------------
describe("POST /tools/call — get_company_facts", () => {
  it("returns company facts when fetch succeeds", async () => {
    const mockData = { cik: 320193, entityName: "Apple Inc.", facts: {} };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await request(app)
      .post("/tools/call")
      .send({ name: "get_company_facts", arguments: { cik: "320193" } });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBeUndefined();
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.entityName).toBe("Apple Inc.");

    vi.restoreAllMocks();
  });

  it("returns INVALID_PARAMS when cik missing", async () => {
    const res = await request(app)
      .post("/tools/call")
      .send({ name: "get_company_facts", arguments: {} });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBe(true);
    expect(res.body.errorCode).toBe("INVALID_PARAMS");
  });
});

// ---------------------------------------------------------------------------
// Test 6: Unknown tool returns canonical error
// ---------------------------------------------------------------------------
describe("POST /tools/call — unknown tool", () => {
  it("returns TOOL_NOT_FOUND for nonexistent tool", async () => {
    const res = await request(app)
      .post("/tools/call")
      .send({ name: "nonexistent_tool", arguments: {} });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBe(true);
    expect(res.body.errorCode).toBe("TOOL_NOT_FOUND");
  });
});

// ---------------------------------------------------------------------------
// Test 7: Vendor HTTP error returns canonical error
// ---------------------------------------------------------------------------
describe("POST /tools/call — vendor error", () => {
  it("returns VENDOR_HTTP_ERROR on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Not Found", { status: 404 }),
    );

    const res = await request(app)
      .post("/tools/call")
      .send({ name: "get_company_facts", arguments: { cik: "9999999999" } });

    expect(res.status).toBe(200);
    expect(res.body.isError).toBe(true);
    expect(res.body.errorCode).toBe("VENDOR_HTTP_ERROR");
    expect(res.body.vendorStatusCode).toBe(404);
    expect(res.body.retryable).toBe(false);

    vi.restoreAllMocks();
  });
});

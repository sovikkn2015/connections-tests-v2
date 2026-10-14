/**
 * SEC EDGAR MCP Adapter — M11-REST TypeScript Reference Implementation.
 * Proves Rule 10 polyglot: identical MCP interface to Python sec-edgar/.
 *
 * Free public API. 10 req/s rate limit. User-Agent required by SEC.
 * Tools: search_filings, get_filing, get_company_facts.
 *
 * Run: tsx src/server.ts
 */

import express, { type Request, type Response, type NextFunction } from "express";
import { randomUUID } from "node:crypto";

// ---------------------------------------------------------------------------
// Configuration (Rule 20: zero credentials in code)
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env.PORT ?? "8070", 10);
const SEC_EDGAR_USER_AGENT =
  process.env.SEC_EDGAR_USER_AGENT ?? "007-FSI-Platform admin@example.com";
const RATE_LIMIT_RPM = parseInt(
  process.env.SEC_EDGAR_RATE_LIMIT_RPM ?? "600",
  10,
);
const RATE_LIMIT_BURST = parseInt(
  process.env.SEC_EDGAR_RATE_LIMIT_BURST ?? "10",
  10,
);

const EFTS_BASE = "https://efts.sec.gov/LATEST";
const DATA_BASE = "https://data.sec.gov";

// ---------------------------------------------------------------------------
// Token-bucket rate limiter (Rule 4)
// ---------------------------------------------------------------------------
class TokenBucket {
  private tokens: number;
  private lastRefill: number;
  private readonly ratePerSecond: number;
  private readonly burst: number;

  constructor(ratePerSecond: number, burst: number) {
    this.ratePerSecond = ratePerSecond;
    this.burst = burst;
    this.tokens = burst;
    this.lastRefill = Date.now();
  }

  acquire(): boolean {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    this.tokens = Math.min(
      this.burst,
      this.tokens + elapsed * this.ratePerSecond,
    );
    this.lastRefill = now;
    if (this.tokens >= 1) {
      this.tokens -= 1;
      return true;
    }
    return false;
  }

  get remaining(): number {
    return Math.floor(this.tokens);
  }
}

const rateLimiter = new TokenBucket(RATE_LIMIT_RPM / 60, RATE_LIMIT_BURST);


// ---------------------------------------------------------------------------
// Canonical error format (matches _shared/errors.py)
// ---------------------------------------------------------------------------
interface CanonicalError {
  isError: true;
  content: Array<{ type: "text"; text: string }>;
  errorCode: string;
  vendorStatusCode: number | null;
  retryable: boolean;
}

interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
}

function canonicalError(
  message: string,
  errorCode = "INTERNAL_ERROR",
  vendorStatusCode: number | null = null,
  retryable = false,
): CanonicalError {
  return {
    isError: true,
    content: [{ type: "text", text: message }],
    errorCode,
    vendorStatusCode,
    retryable,
  };
}

function toolResult(data: unknown): ToolResult {
  const text = typeof data === "string" ? data : JSON.stringify(data);
  return { content: [{ type: "text", text }] };
}

// ---------------------------------------------------------------------------
// SEC EDGAR HTTP client
// ---------------------------------------------------------------------------
async function secGet(
  url: string,
  params?: Record<string, string | number>,
): Promise<CanonicalError | unknown> {
  if (!rateLimiter.acquire()) {
    return canonicalError(
      "SEC EDGAR rate limit exceeded.",
      "RATE_LIMIT_EXCEEDED",
      429,
      true,
    );
  }

  const u = new URL(url);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      u.searchParams.set(k, String(v));
    }
  }

  const resp = await fetch(u.toString(), {
    headers: {
      "User-Agent": SEC_EDGAR_USER_AGENT,
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(30_000),
  });

  if (!resp.ok) {
    return canonicalError(
      `SEC EDGAR returned HTTP ${resp.status}`,
      "VENDOR_HTTP_ERROR",
      resp.status,
      resp.status >= 500,
    );
  }

  return resp.json();
}

// ---------------------------------------------------------------------------
// Tool definitions (identical JSON Schema to Python version)
// ---------------------------------------------------------------------------
interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  status: string;
}

const TOOL_DEFINITIONS: ToolDefinition[] = [
  {
    name: "search_filings",
    description:
      "Search SEC EDGAR filings by company ticker/name, filing type, and date range.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description:
            "Company ticker symbol or name (e.g. 'AAPL' or 'Apple Inc')",
        },
        filing_type: {
          type: "string",
          description: "SEC filing type filter",
          enum: ["10-K", "10-Q", "8-K", "13F", "S-1", "DEF 14A", "4", "SC 13D"],
        },
        date_range: {
          type: "string",
          description: "Date range in format 'YYYY-MM-DD:YYYY-MM-DD'",
          pattern: "^\\d{4}-\\d{2}-\\d{2}:\\d{4}-\\d{2}-\\d{2}$",
        },
        limit: {
          type: "integer",
          description: "Max results (1-40)",
          minimum: 1,
          maximum: 40,
          default: 10,
        },
      },
      required: ["query"],
      additionalProperties: false,
    },
    status: "active",
  },
  {
    name: "get_filing",
    description: "Retrieve SEC filing metadata by accession number.",
    inputSchema: {
      type: "object",
      properties: {
        accession_number: {
          type: "string",
          description:
            "SEC accession number (e.g. '0000320193-23-000106')",
        },
      },
      required: ["accession_number"],
      additionalProperties: false,
    },
    status: "active",
  },
  {
    name: "get_company_facts",
    description:
      "Get XBRL company facts (financial data) for a company by CIK number.",
    inputSchema: {
      type: "object",
      properties: {
        cik: {
          type: "string",
          description:
            "SEC Central Index Key (CIK) number (e.g. '320193' for Apple)",
        },
      },
      required: ["cik"],
      additionalProperties: false,
    },
    status: "active",
  },
];


// ---------------------------------------------------------------------------
// Tool handlers (vendor-specific logic only)
// ---------------------------------------------------------------------------
type ToolHandler = (
  args: Record<string, unknown>,
) => Promise<CanonicalError | ToolResult>;

async function handleSearchFilings(
  args: Record<string, unknown>,
): Promise<CanonicalError | ToolResult> {
  const query = args.query as string | undefined;
  if (!query) {
    return canonicalError("'query' is required.", "INVALID_PARAMS");
  }
  const params: Record<string, string | number> = {
    q: query,
    from: 0,
    size: (args.limit as number) ?? 10,
  };
  if (args.date_range) params.dateRange = args.date_range as string;
  if (args.filing_type) params.forms = args.filing_type as string;

  const result = await secGet(`${EFTS_BASE}/search-index`, params);
  if (isCanonicalError(result)) return result;
  return toolResult(result);
}

async function handleGetFiling(
  args: Record<string, unknown>,
): Promise<CanonicalError | ToolResult> {
  const accession = args.accession_number as string | undefined;
  if (!accession) {
    return canonicalError("'accession_number' is required.", "INVALID_PARAMS");
  }
  const clean = accession.replace(/-/g, "");
  const result = await secGet(`${DATA_BASE}/submissions/${clean}.json`);
  if (isCanonicalError(result)) return result;
  return toolResult(result);
}

async function handleGetCompanyFacts(
  args: Record<string, unknown>,
): Promise<CanonicalError | ToolResult> {
  const cik = args.cik as string | undefined;
  if (!cik) {
    return canonicalError("'cik' is required.", "INVALID_PARAMS");
  }
  const padded = cik.padStart(10, "0");
  const result = await secGet(
    `${DATA_BASE}/api/xbrl/companyfacts/CIK${padded}.json`,
  );
  if (isCanonicalError(result)) return result;
  return toolResult(result);
}

function isCanonicalError(v: unknown): v is CanonicalError {
  return typeof v === "object" && v !== null && (v as CanonicalError).isError === true;
}

const TOOL_HANDLERS: Record<string, ToolHandler> = {
  search_filings: handleSearchFilings,
  get_filing: handleGetFiling,
  get_company_facts: handleGetCompanyFacts,
};

// ---------------------------------------------------------------------------
// Express app — MCP interface (GET / + POST /tools/list + POST /tools/call)
// ---------------------------------------------------------------------------
export const app = express();
app.use(express.json());

// Request context middleware (structured logging + request ID)
app.use((req: Request, res: Response, next: NextFunction) => {
  const requestId = (req.headers["x-request-id"] as string) ?? randomUUID();
  res.setHeader("x-request-id", requestId);
  res.setHeader("x-rate-limit-remaining", String(rateLimiter.remaining));
  const start = Date.now();
  res.on("finish", () => {
    const duration = Date.now() - start;
    console.log(
      JSON.stringify({
        event: "request_completed",
        method: req.method,
        path: req.path,
        status: res.statusCode,
        duration_ms: duration,
        request_id: requestId,
      }),
    );
  });
  next();
});

// GET / — Server info + health check (Rule 16)
app.get("/", (_req: Request, res: Response) => {
  res.json({
    name: "sec-edgar-ts-adapter",
    version: "1.0.0",
    vendor: "sec_edgar",
    description:
      "SEC EDGAR public filings search and retrieval (TypeScript). Free API, 10 req/s.",
    capabilities: { tools: true },
    status: "healthy",
  });
});

// POST /tools/list — Capability discovery with JSON Schema (Rule 2)
app.post("/tools/list", (_req: Request, res: Response) => {
  res.json({ tools: TOOL_DEFINITIONS });
});

// POST /tools/call — Tool execution
app.post("/tools/call", async (req: Request, res: Response) => {
  const { name, arguments: args = {} } = req.body as {
    name?: string;
    arguments?: Record<string, unknown>;
  };

  if (!name || !(name in TOOL_HANDLERS)) {
    res.json(
      canonicalError(
        `Unknown tool: ${name ?? "(none)"}`,
        "TOOL_NOT_FOUND",
        404,
        false,
      ),
    );
    return;
  }

  const start = Date.now();
  try {
    const result = await TOOL_HANDLERS[name](args);
    const duration = Date.now() - start;
    console.log(
      JSON.stringify({
        event: "tool_call_success",
        tool_name: name,
        duration_ms: duration,
      }),
    );
    res.json(result);
  } catch (err) {
    const duration = Date.now() - start;
    const message = err instanceof Error ? err.message : String(err);
    console.error(
      JSON.stringify({
        event: "tool_call_error",
        tool_name: name,
        duration_ms: duration,
        error: message,
      }),
    );
    res.json(canonicalError(message, "TOOL_EXECUTION_ERROR", null, false));
  }
});

// ---------------------------------------------------------------------------
// Start server (only when run directly, not when imported for tests)
// ---------------------------------------------------------------------------
const isDirectRun =
  process.argv[1]?.endsWith("server.ts") ||
  process.argv[1]?.endsWith("server.js");

if (isDirectRun) {
  app.listen(PORT, () => {
    console.log(
      JSON.stringify({
        event: "server_started",
        name: "sec-edgar-ts-adapter",
        port: PORT,
        user_agent: SEC_EDGAR_USER_AGENT,
      }),
    );
  });
}

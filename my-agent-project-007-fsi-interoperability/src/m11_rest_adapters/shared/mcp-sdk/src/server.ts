/**
 * McpServer — fastify harness enforcing the 3-endpoint MCP contract.
 * Spec R1: GET /, POST /tools/list, POST /tools/call. No 4th endpoint (AC1.4).
 *
 * Emits `mcp.tool_call.start` + `mcp.tool_call.end` per AC7.4.
 * Validates inputs with Zod before vendor calls (AC8.3).
 * Returns canonical error body per AC1.3 / AC14.2.
 */

import Fastify, {
  type FastifyInstance,
  type FastifyReply,
  type FastifyRequest,
} from "fastify";
import { randomUUID } from "node:crypto";
import { ZodError } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

import { AdapterError, makeErrorBody, httpStatusFor } from "./errors.js";
import type { Logger } from "./logger.js";
import type {
  AdapterConfig,
  HealthCheckResult,
  McpCallResponse,
  ToolDefinition,
  ToolDescriptor,
} from "./types.js";

export interface McpServerOptions {
  readonly config: AdapterConfig;
  readonly logger: Logger;
  readonly tools: Readonly<Record<string, ToolDefinition>>;
  readonly healthCheck: () => Promise<HealthCheckResult>;
}

export class AdapterAlreadyRunning extends Error {
  constructor() {
    super("AdapterAlreadyRunning: startServer was called more than once");
    this.name = "AdapterAlreadyRunning";
  }
}

const MAX_BODY_BYTES = 1024 * 1024; // 1 MiB (AC1.8)

/** Build the fastify app (does not listen). Exposed for testing. */
export function buildMcpApp(opts: McpServerOptions): FastifyInstance {
  const { config, logger, tools, healthCheck } = opts;
  const app = Fastify({
    logger: false,
    bodyLimit: MAX_BODY_BYTES,
    disableRequestLogging: true,
    trustProxy: false,
  });

  // Alphabetically-sorted tool descriptors — AC1.2 + AC2.8.
  const descriptors: readonly ToolDescriptor[] = Object.freeze(
    Object.values(tools)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: zodToJsonSchema(t.input, {
          target: "jsonSchema7",
          $refStrategy: "none",
        }) as ToolDescriptor["inputSchema"],
      })),
  );
  const toolNames: readonly string[] = descriptors.map((d) => d.name);

  app.addHook("onSend", async (_req, reply, payload) => {
    reply.header("Content-Type", "application/json; charset=utf-8");
    reply.header("X-Adapter-Version", config.adapterVersion);
    return payload;
  });

  // Replace default parser — return 415 for non-JSON bodies.
  app.removeContentTypeParser(["application/json"]);
  app.addContentTypeParser(
    "application/json",
    { parseAs: "string" },
    (_req, body, done) => {
      try {
        done(null, body === "" ? {} : JSON.parse(body as string));
      } catch (err) {
        done(err as Error, undefined);
      }
    },
  );

  function injectTrace(req: FastifyRequest, reply: FastifyReply): string {
    const existing = req.headers["x-trace-id"];
    const trace =
      typeof existing === "string" && existing.length > 0
        ? existing
        : randomUUID();
    reply.header("X-Trace-Id", trace);
    return trace;
  }

  function sendError(
    reply: FastifyReply,
    trace: string,
    err: AdapterError,
  ): FastifyReply {
    reply.header("X-Trace-Id", trace);
    return reply.status(httpStatusFor(err.code)).send({
      result: null,
      error: makeErrorBody(err.code, err.message, err.vendorStatusCode),
    } satisfies McpCallResponse);
  }

  // AC1.1 — GET / — server info + health check (double duty AC1.6, AC9.8).
  app.get("/", async (req, reply) => {
    const trace = injectTrace(req, reply);
    let health: HealthCheckResult;
    try {
      health = await healthCheck();
    } catch (err) {
      logger.error({
        event: "health_check_error",
        err: String(err),
        trace_id: trace,
      });
      health = {
        status: "degraded",
        checks: { oauth: "unknown" as const, circuit: "degraded", mtls: "degraded" },
        reason: "health_check_threw",
      };
    }
    const body = {
      type: "mcp-server",
      version: config.adapterVersion,
      vendor: config.vendor,
      schemaVersion: config.adapterVersion,
      vendorApiVersion: config.vendorApiVersion,
      tools: toolNames,
      status: health.status,
      checks: health.checks,
      ...(health.reason ? { reason: health.reason } : {}),
    };
    const status = health.status === "ok" ? 200 : 503;
    return reply.status(status).send(body);
  });

  // AC1.2 — POST /tools/list.
  app.post("/tools/list", async (req, reply) => {
    injectTrace(req, reply);
    return reply.status(200).send({ tools: descriptors });
  });

  // AC1.3 — POST /tools/call.
  app.post("/tools/call", async (req, reply) => {
    const trace = injectTrace(req, reply);
    const started = Date.now();

    // AC1.8 — enforce JSON content-type.
    const ct = String(req.headers["content-type"] ?? "");
    if (!ct.toLowerCase().startsWith("application/json")) {
      return sendError(
        reply,
        trace,
        new AdapterError(
          "unsupported_media_type",
          "Content-Type must be application/json",
        ),
      );
    }

    // AC5.4 — per-firm isolation requires X-Firm-ID.
    const firmHdr = req.headers["x-firm-id"];
    const firmId =
      typeof firmHdr === "string" && firmHdr.length > 0 ? firmHdr : null;
    if (config.firmIdRequired && !firmId) {
      return sendError(
        reply,
        trace,
        new AdapterError("missing_firm_id", "X-Firm-ID header is required"),
      );
    }

    const body = req.body as { name?: unknown; arguments?: unknown } | null;
    if (!body || typeof body !== "object") {
      return sendError(
        reply,
        trace,
        new AdapterError("invalid_arguments", "request body must be an object"),
      );
    }
    const name = typeof body.name === "string" ? body.name : "";
    const tool = tools[name];
    if (!tool) {
      return sendError(
        reply,
        trace,
        new AdapterError(
          "tool_not_found",
          `tool not registered: ${name || "(unset)"}`,
        ),
      );
    }

    logger.info({
      event: "mcp.tool_call.start",
      tool_name: name,
      firm_id: firmId ?? "(unset)",
      trace_id: trace,
    });

    // AC8.3 — Zod validation BEFORE vendor call, OAuth refresh, rate-limit.
    const parsed = tool.input.safeParse(body.arguments);
    if (!parsed.success) {
      const msg = zodPathOnlyMessage(parsed.error);
      logger.info({
        event: "mcp.tool_call.invalid_args",
        tool_name: name,
        error_path: msg,
        trace_id: trace,
      });
      return sendError(
        reply,
        trace,
        new AdapterError("invalid_arguments", msg),
      );
    }

    try {
      const result = await tool.handler(parsed.data, {
        firmId: firmId ?? "",
        traceId: trace,
        toolName: name,
      });

      // Optional strict-output enforcement (eMoney).
      if (tool.output) {
        const outParsed = tool.output.safeParse(result);
        if (!outParsed.success) {
          // For eMoney, handlers raise emoney_raw_plan_forbidden themselves;
          // a mismatch at this layer is an adapter-internal contract bug.
          throw new AdapterError(
            "vendor_error",
            "adapter output failed strict validation",
            null,
          );
        }
      }

      const duration = Date.now() - started;
      logger.info({
        event: "mcp.tool_call.end",
        tool_name: name,
        status_code: 200,
        duration_ms: duration,
        vendor_status_code: null,
        retry_count: 0,
        circuit_state: "CLOSED",
        trace_id: trace,
      });
      return reply.status(200).send({
        result,
        error: null,
      } satisfies McpCallResponse);
    } catch (err) {
      const duration = Date.now() - started;
      const adapterErr =
        err instanceof AdapterError
          ? err
          : new AdapterError("vendor_error", safeMessage(err), null);
      logger.info({
        event: "mcp.tool_call.end",
        tool_name: name,
        status_code: httpStatusFor(adapterErr.code),
        duration_ms: duration,
        vendor_status_code: adapterErr.vendorStatusCode,
        retry_count: 0,
        circuit_state: "CLOSED",
        trace_id: trace,
      });
      return sendError(reply, trace, adapterErr);
    }
  });

  // AC1.4 — any other route → 404.
  app.setNotFoundHandler((req, reply) => {
    injectTrace(req, reply);
    return reply.status(404).send({
      result: null,
      error: makeErrorBody("tool_not_found", `no such endpoint: ${req.url}`),
    });
  });

  app.setErrorHandler((err, req, reply) => {
    injectTrace(req, reply);
    if ((err as { statusCode?: number }).statusCode === 413) {
      return reply.status(413).send({
        result: null,
        error: makeErrorBody(
          "payload_too_large",
          "body exceeds 1 MiB (AC1.8)",
        ),
      });
    }
    if (err instanceof SyntaxError) {
      return reply.status(415).send({
        result: null,
        error: makeErrorBody(
          "unsupported_media_type",
          "invalid JSON body",
        ),
      });
    }
    logger.error({ event: "fastify_error", err: safeMessage(err) });
    return reply.status(500).send({
      result: null,
      error: makeErrorBody("vendor_error", "internal adapter error"),
    });
  });

  return app;
}

function zodPathOnlyMessage(err: ZodError): string {
  // AC8.4 — path only, NO values.
  return err.issues
    .map((i) => {
      const path = i.path.length > 0 ? i.path.join(".") : "(root)";
      return `arguments.${path}: ${i.code}`;
    })
    .join("; ");
}

function safeMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

/** Run server; second call throws AdapterAlreadyRunning (AC13.3). */
let started = false;
export async function startServer(
  opts: McpServerOptions,
): Promise<FastifyInstance> {
  if (started) throw new AdapterAlreadyRunning();
  started = true;
  const app = buildMcpApp(opts);
  await app.listen({ port: opts.config.port, host: "0.0.0.0" });
  return app;
}

/** Reset the single-instance guard (for tests only). */
export function __resetStartedForTests(): void {
  started = false;
}

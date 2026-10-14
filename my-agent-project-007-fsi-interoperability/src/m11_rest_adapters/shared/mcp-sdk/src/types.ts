/**
 * Shared MCP SDK types — MCP envelope + AdapterConfig + tool descriptor.
 * Spec AC1.1-1.3, AC13.2.
 */

import type { JSONSchema7 } from "./vendor/json-schema.js";
import type { ZodTypeAny } from "zod";

export type CanonicalVendor =
  | "salesforce_fsc"
  | "orion"
  | "emoney"
  | "schwab"
  | "smarsh";

export interface ToolDescriptor {
  readonly name: string;
  readonly description: string;
  readonly inputSchema: JSONSchema7;
}

export interface ToolDefinition {
  readonly name: string;
  readonly description: string;
  readonly input: ZodTypeAny;
  /** Optional strict output schema (eMoney uses this; others pass through). */
  readonly output?: ZodTypeAny;
  readonly handler: (args: unknown, ctx: ToolInvocationContext) => Promise<unknown>;
}

export interface ToolInvocationContext {
  readonly firmId: string;
  readonly traceId: string;
  readonly toolName: string;
}

export interface McpErrorBody {
  readonly code: string;
  readonly message: string;
  readonly vendorStatusCode: number | null;
  readonly retryable: boolean;
}

export interface McpCallResponse<T = unknown> {
  readonly result: T | null;
  readonly error: McpErrorBody | null;
}

export interface AdapterConfig {
  readonly vendor: CanonicalVendor;
  readonly adapterVersion: string;
  readonly vendorApiVersion: string;
  readonly port: number;
  readonly httpTimeoutMs: number;
  readonly undiciConnections: number;
  readonly egressAllowlist: readonly string[];
  readonly mtls: MtlsConfig;
  readonly firmIdRequired: boolean;
}

export interface MtlsConfig {
  readonly clientCertPath: string;
  readonly clientKeyPath: string;
  readonly caCertPath: string;
  readonly trustedSubjectCn: string;
  readonly enabled: boolean;
}

export interface HealthCheckResult {
  readonly status: "ok" | "degraded";
  readonly checks: {
    readonly oauth: "ok" | "degraded" | "unknown";
    readonly circuit: "ok" | "degraded";
    readonly mtls: "ok" | "degraded";
  };
  readonly reason?: string;
}

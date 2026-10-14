/**
 * @project-007/mcp-sdk — barrel module.
 * Explicit named exports only (AC3.8).
 */

export {
  VALID_ADAPTER_ERROR_CODES,
  AdapterError,
  makeErrorBody,
  httpStatusFor,
  isRetryable,
} from "./errors.js";
export type { AdapterErrorCode } from "./errors.js";

export type {
  AdapterConfig,
  CanonicalVendor,
  HealthCheckResult,
  McpCallResponse,
  McpErrorBody,
  MtlsConfig,
  ToolDefinition,
  ToolDescriptor,
  ToolInvocationContext,
} from "./types.js";

export { SystemClock, FakeClock } from "./clock.js";
export type { Clock } from "./clock.js";

export { FakeSecretsClient, buildSecretsClient } from "./secrets.js";
export type { SecretsClient, SecretsBackend } from "./secrets.js";

export { getLogger, DEFAULT_REDACT_PATHS } from "./logger.js";
export type { Logger } from "./logger.js";

export {
  validateVendorURL,
  assertVendorURLSafe,
  hostMatchesAllowlist,
  classifyIPv4,
  classifyIPv6,
} from "./ssrf.js";
export type { SsrfOptions, SsrfResult, SsrfFailure } from "./ssrf.js";

export { LRUCache } from "./lru.js";

export { CircuitBreaker } from "./circuit.js";
export type { CircuitState, CircuitBreakerConfig } from "./circuit.js";

export {
  TokenBucket,
  DailyBucket,
  RateLimiterRegistry,
  parseRetryAfter,
} from "./rate_limit.js";
export type { BucketConfig, AcquireResult } from "./rate_limit.js";

export { VendorHttpClient, mapVendorStatusToErrorCode } from "./http_client.js";
export type {
  HttpClientConfig,
  VendorCallOptions,
  VendorCallResult,
} from "./http_client.js";

export {
  buildMcpApp,
  startServer,
  AdapterAlreadyRunning,
  __resetStartedForTests,
} from "./server.js";
export type { McpServerOptions } from "./server.js";

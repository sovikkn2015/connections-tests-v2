/**
 * Canonical M11 adapter error codes (22 codes v0.2.0).
 * Spec AC16.3.
 */

import type { McpErrorBody } from "./types.js";

/** Frozen 22-code error-code vocabulary per AC16.3 v0.2.0. */
export const VALID_ADAPTER_ERROR_CODES = Object.freeze([
  "tool_not_found",
  "invalid_arguments",
  "missing_firm_id",
  "unsupported_media_type",
  "payload_too_large",
  "adapter_timeout",
  "rate_limit_exceeded",
  "vendor_rate_limit",
  "vendor_bad_request",
  "vendor_auth_failed",
  "vendor_forbidden",
  "vendor_not_found",
  "vendor_conflict",
  "vendor_unprocessable",
  "vendor_error",
  "vendor_timeout",
  "vendor_circuit_open",
  "vendor_invalid_json",
  "emoney_raw_plan_forbidden",
  "startup_version_mismatch",
  "mtls_degraded",
  "vendor_ssrf_blocked",
] as const);

export type AdapterErrorCode = (typeof VALID_ADAPTER_ERROR_CODES)[number];

const HTTP_STATUS: Record<AdapterErrorCode, number> = {
  tool_not_found: 404,
  invalid_arguments: 400,
  missing_firm_id: 400,
  unsupported_media_type: 415,
  payload_too_large: 413,
  adapter_timeout: 504,
  rate_limit_exceeded: 429,
  vendor_rate_limit: 429,
  vendor_bad_request: 400,
  vendor_auth_failed: 401,
  vendor_forbidden: 403,
  vendor_not_found: 404,
  vendor_conflict: 409,
  vendor_unprocessable: 422,
  vendor_error: 502,
  vendor_timeout: 504,
  vendor_circuit_open: 503,
  vendor_invalid_json: 502,
  emoney_raw_plan_forbidden: 502,
  startup_version_mismatch: 500,
  mtls_degraded: 503,
  vendor_ssrf_blocked: 502,
};

const RETRYABLE: Record<AdapterErrorCode, boolean> = {
  tool_not_found: false,
  invalid_arguments: false,
  missing_firm_id: false,
  unsupported_media_type: false,
  payload_too_large: false,
  adapter_timeout: true,
  rate_limit_exceeded: true,
  vendor_rate_limit: true,
  vendor_bad_request: false,
  vendor_auth_failed: false,
  vendor_forbidden: false,
  vendor_not_found: false,
  vendor_conflict: false,
  vendor_unprocessable: false,
  vendor_error: true,
  vendor_timeout: true,
  vendor_circuit_open: true,
  vendor_invalid_json: true,
  emoney_raw_plan_forbidden: false,
  startup_version_mismatch: false,
  mtls_degraded: true,
  vendor_ssrf_blocked: false,
};

export function httpStatusFor(code: AdapterErrorCode): number {
  return HTTP_STATUS[code];
}

export function isRetryable(code: AdapterErrorCode): boolean {
  return RETRYABLE[code];
}

export class AdapterError extends Error {
  public readonly code: AdapterErrorCode;
  public readonly vendorStatusCode: number | null;
  public readonly retryable: boolean;

  constructor(
    code: AdapterErrorCode,
    message: string,
    vendorStatusCode: number | null = null,
  ) {
    super(message);
    this.name = "AdapterError";
    this.code = code;
    this.vendorStatusCode = vendorStatusCode;
    this.retryable = RETRYABLE[code];
  }

  toMcpBody(): McpErrorBody {
    return {
      code: this.code,
      message: this.message,
      vendorStatusCode: this.vendorStatusCode,
      retryable: this.retryable,
    };
  }
}

export function makeErrorBody(
  code: AdapterErrorCode,
  message: string,
  vendorStatusCode: number | null = null,
): McpErrorBody {
  return {
    code,
    message,
    vendorStatusCode,
    retryable: RETRYABLE[code],
  };
}

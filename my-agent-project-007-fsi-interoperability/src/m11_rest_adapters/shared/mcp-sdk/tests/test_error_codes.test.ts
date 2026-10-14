/**
 * Error-code vocabulary tests. Spec AC16.3 — 22 codes.
 */

import { describe, it, expect } from "vitest";

import {
  AdapterError,
  VALID_ADAPTER_ERROR_CODES,
  httpStatusFor,
  isRetryable,
  makeErrorBody,
} from "../src/errors.js";

describe("VALID_ADAPTER_ERROR_CODES — AC16.3 v0.2.0", () => {
  it("contains exactly 22 codes", () => {
    expect(VALID_ADAPTER_ERROR_CODES.length).toBe(22);
    expect(new Set(VALID_ADAPTER_ERROR_CODES).size).toBe(22);
  });

  it("includes vendor_ssrf_blocked (v0.2.0 new)", () => {
    expect(VALID_ADAPTER_ERROR_CODES).toContain("vendor_ssrf_blocked");
  });

  it("maps vendor_conflict to HTTP 409 (SFDC 412 → 409, AC8.9)", () => {
    expect(httpStatusFor("vendor_conflict")).toBe(409);
    expect(isRetryable("vendor_conflict")).toBe(false);
  });

  it("maps rate_limit_exceeded to HTTP 429 retryable", () => {
    expect(httpStatusFor("rate_limit_exceeded")).toBe(429);
    expect(isRetryable("rate_limit_exceeded")).toBe(true);
  });

  it("maps emoney_raw_plan_forbidden to 502 non-retryable", () => {
    expect(httpStatusFor("emoney_raw_plan_forbidden")).toBe(502);
    expect(isRetryable("emoney_raw_plan_forbidden")).toBe(false);
  });

  it("maps vendor_ssrf_blocked to 502 non-retryable", () => {
    expect(httpStatusFor("vendor_ssrf_blocked")).toBe(502);
    expect(isRetryable("vendor_ssrf_blocked")).toBe(false);
  });
});

describe("AdapterError.toMcpBody — AC14.2 minimal body", () => {
  it("includes only allowed fields", () => {
    const err = new AdapterError("vendor_error", "boom", 503);
    const body = err.toMcpBody();
    expect(Object.keys(body).sort()).toEqual(
      ["code", "message", "retryable", "vendorStatusCode"].sort(),
    );
    expect(body.code).toBe("vendor_error");
    expect(body.vendorStatusCode).toBe(503);
    expect(body.retryable).toBe(true);
  });
});

describe("makeErrorBody", () => {
  it("returns readonly-shape object", () => {
    const body = makeErrorBody("invalid_arguments", "arguments.clientId: regex");
    expect(body.code).toBe("invalid_arguments");
    expect(body.vendorStatusCode).toBe(null);
    expect(body.retryable).toBe(false);
  });
});

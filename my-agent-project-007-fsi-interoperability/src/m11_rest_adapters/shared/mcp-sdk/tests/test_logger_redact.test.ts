/**
 * Logger redaction tests. Spec AC7.2, AC7.7.
 * Ensures PII + tokens never hit stdout.
 */

import { describe, it, expect } from "vitest";
import { PassThrough } from "node:stream";

import { DEFAULT_REDACT_PATHS, getLogger } from "../src/logger.js";

function captureLogOutput(fn: (logger: ReturnType<typeof getLogger>) => void): string {
  const sink = new PassThrough();
  let buf = "";
  sink.on("data", (chunk) => {
    buf += String(chunk);
  });
  const logger = getLogger({
    adapterName: "m11-test",
    vendor: "salesforce_fsc",
    destination: sink,
  });
  fn(logger);
  return buf;
}

describe("pino redact rules — AC7.2", () => {
  it("includes authorization header + PII paths + wildcards", () => {
    for (const p of [
      "req.headers.authorization",
      "req.body.arguments.ssn",
      "req.body.arguments.taxId",
      "req.body.arguments.email",
      "req.body.arguments.dateOfBirth",
      "err.response.data",
      "*.password",
      "*.token",
      "*.access_token",
      "*.refresh_token",
      "*.private_key",
    ]) {
      expect(DEFAULT_REDACT_PATHS).toContain(p);
    }
  });

  it("redacts access_token literal (AC7.7)", () => {
    const out = captureLogOutput((log) => {
      log.info(
        {
          event: "auth.sfdc.token_acquired",
          access_token: "00D5f000004fvFf!AQEAQEXAMPLE",
        },
        "token event",
      );
    });
    expect(out).not.toContain("AQEAQEXAMPLE");
    expect(out).toContain("[REDACTED]");
  });

  it("redacts authorization header literal", () => {
    const out = captureLogOutput((log) => {
      log.info(
        {
          req: { headers: { authorization: "Bearer sk_live_SECRETLEAK" } },
        },
        "header",
      );
    });
    expect(out).not.toContain("sk_live_SECRETLEAK");
  });

  it("redacts nested password key via wildcard", () => {
    const out = captureLogOutput((log) => {
      log.info(
        {
          creds: { username: "alice", password: "hunter2" },
        },
        "creds",
      );
    });
    expect(out).not.toContain("hunter2");
    expect(out).toContain('"username":"alice"');
  });
});

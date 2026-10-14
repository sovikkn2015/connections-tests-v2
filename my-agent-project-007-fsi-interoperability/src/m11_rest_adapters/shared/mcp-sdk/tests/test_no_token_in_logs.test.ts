/**
 * End-to-end log-leak test. Spec AC4.5, AC7.7.
 *
 * Fires log lines with synthetic placeholder values, then greps the stdout
 * capture for the literals. Any hit fails. No real credentials — all
 * placeholders are clearly marked DONOTLEAK.
 */

import { describe, it, expect } from "vitest";
import { PassThrough } from "node:stream";

import { getLogger } from "../src/logger.js";

describe("AC7.7 — PII + token never appear in log output", () => {
  it("captures common secret shapes", () => {
    const sink = new PassThrough();
    let out = "";
    sink.on("data", (c) => {
      out += String(c);
    });
    const log = getLogger({
      adapterName: "m11-test",
      vendor: "salesforce_fsc",
      destination: sink,
    });

    const SECRETS = {
      accessToken: "placeholder_access_DONOTLEAK_AAA",
      refreshToken: "placeholder_refresh_DONOTLEAK_BBB",
      privateKeyPEM: "PLACEHOLDER_PRIVATE_KEY_DONOTLEAK",
      clientSecret: "placeholder_cs_DONOTLEAK",
      password: "placeholder_pw_DONOTLEAK",
      ssn: "555-12-3456",
      authorization: "Bearer placeholder_auth_DONOTLEAK",
    };

    log.info(
      {
        event: "auth.test",
        access_token: SECRETS.accessToken,
        refresh_token: SECRETS.refreshToken,
        privateKeyPEM: SECRETS.privateKeyPEM,
        client_secret: SECRETS.clientSecret,
        password: SECRETS.password,
        ssn: SECRETS.ssn,
        req: {
          headers: { authorization: SECRETS.authorization },
          body: { arguments: { ssn: SECRETS.ssn } },
        },
      },
      "e2e-redact-check",
    );

    for (const [label, value] of Object.entries(SECRETS)) {
      expect(out.includes(value), `leak: ${label}`).toBe(false);
    }
    expect(out).toContain("[REDACTED]");
  });
});

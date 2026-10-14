import { describe, it, expect } from "vitest";
import { PassThrough } from "node:stream";

import {
  FakeClock,
  FakeSecretsClient,
  getLogger,
  AdapterError,
  type Logger,
} from "@project-007/mcp-sdk";

import { SchwabAuthClient } from "../src/auth.js";

function captureLogger(): { logger: Logger; out: () => string } {
  const sink = new PassThrough();
  let out = "";
  sink.on("data", (c) => (out += String(c)));
  return {
    logger: getLogger({
      adapterName: "t",
      vendor: "schwab",
      destination: sink,
      level: "trace",
    }),
    out: () => out,
  };
}

function stubFetch(opts: { status: number; body: string }): unknown {
  return async () => ({
    statusCode: opts.status,
    headers: {},
    body: { text: async () => opts.body },
  });
}

function makeSecrets(): FakeSecretsClient {
  return new FakeSecretsClient({
    "m11/schwab/oauth_credentials": {
      clientId: "cid_placeholder",
      clientSecret: "cs_placeholder_DONOTLEAK",
    },
    "m11/schwab/refresh_token": "rt_initial_DONOTLEAK",
  });
}

describe("Schwab RT rotation — AC4.7 success path", () => {
  it("persists new RT to Secrets after refresh", async () => {
    const { logger } = captureLogger();
    const secrets = makeSecrets();
    const auth = new SchwabAuthClient({
      secrets,
      credentialsPath: "m11/schwab/oauth_credentials",
      refreshTokenPath: "m11/schwab/refresh_token",
      tokenUrl: "https://api.schwabapi.com/v1/oauth/token",
      clock: new FakeClock(0),
      logger,
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_rotated_DONOTLEAK",
          refresh_token: "rt_rotated_DONOTLEAK",
          expires_in: 1800,
        }),
      }) as never,
    });
    const tok = await auth.getToken("acme");
    expect(tok.accessToken).toBe("at_rotated_DONOTLEAK");
    expect(secrets.setSecretCalls.length).toBe(1);
    expect(secrets.setSecretCalls[0]!.path).toBe("m11/schwab/refresh_token");
    expect(secrets.setSecretCalls[0]!.value).toBe("rt_rotated_DONOTLEAK");
  });
});

describe("Schwab RT rotation — AC4.13 CRITICAL alert on setSecret failure", () => {
  it("emits severity:CRITICAL event when setSecret throws; does NOT crash", async () => {
    const cap = captureLogger();
    const secrets = makeSecrets();
    secrets.setSecretFailureCount = 1;
    const auth = new SchwabAuthClient({
      secrets,
      credentialsPath: "m11/schwab/oauth_credentials",
      refreshTokenPath: "m11/schwab/refresh_token",
      tokenUrl: "https://api.schwabapi.com/v1/oauth/token",
      clock: new FakeClock(0),
      logger: cap.logger,
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_rotated_DONOTLEAK",
          refresh_token: "rt_new_DONOTLEAK",
          expires_in: 1800,
        }),
      }) as never,
    });
    const tok = await auth.getToken("acme");
    expect(tok.accessToken).toBe("at_rotated_DONOTLEAK");
    expect(auth.healthy()).toBe(false);
    const out = cap.out();
    expect(out).toContain("auth.schwab.rt_rotation_failed");
    expect(out).toContain("CRITICAL");
  });
});

describe("Schwab RT rotation — failure modes", () => {
  it("400 invalid_grant raises vendor_auth_failed + fatal log", async () => {
    const cap = captureLogger();
    const secrets = makeSecrets();
    const auth = new SchwabAuthClient({
      secrets,
      credentialsPath: "m11/schwab/oauth_credentials",
      refreshTokenPath: "m11/schwab/refresh_token",
      tokenUrl: "https://api.schwabapi.com/v1/oauth/token",
      clock: new FakeClock(0),
      logger: cap.logger,
      fetchImpl: stubFetch({
        status: 400,
        body: JSON.stringify({ error: "invalid_grant" }),
      }) as never,
    });
    await expect(auth.getToken("acme")).rejects.toThrow(AdapterError);
    expect(cap.out()).toContain("auth.schwab.rt_invalid_grant");
  });

  it("missing access_token in response raises vendor_auth_failed", async () => {
    const { logger } = captureLogger();
    const secrets = makeSecrets();
    const auth = new SchwabAuthClient({
      secrets,
      credentialsPath: "m11/schwab/oauth_credentials",
      refreshTokenPath: "m11/schwab/refresh_token",
      tokenUrl: "https://api.schwabapi.com/v1/oauth/token",
      clock: new FakeClock(0),
      logger,
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({ refresh_token: "only_rt_DONOTLEAK" }),
      }) as never,
    });
    await expect(auth.getToken("acme")).rejects.toThrow(AdapterError);
  });
});

describe("SIGTERM — AC17.3 wait <= 10s for in-flight rotation", () => {
  it("waitForRotation resolves when no rotation in-flight", async () => {
    const { logger } = captureLogger();
    const auth = new SchwabAuthClient({
      secrets: makeSecrets(),
      credentialsPath: "m11/schwab/oauth_credentials",
      refreshTokenPath: "m11/schwab/refresh_token",
      tokenUrl: "https://api.schwabapi.com/v1/oauth/token",
      clock: new FakeClock(0),
      logger,
      fetchImpl: stubFetch({ status: 200, body: "{}" }) as never,
    });
    await auth.waitForRotation(100);
    expect(true).toBe(true);
  });
});

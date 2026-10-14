/**
 * SFDC auth + SSRF + LRU tests. Spec AC4.1, AC4.2, AC4.5, AC4.14, AC14.10.
 */

import { describe, it, expect } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { PassThrough } from "node:stream";

import {
  FakeClock,
  FakeSecretsClient,
  getLogger,
  AdapterError,
} from "@project-007/mcp-sdk";

import {
  SfdcAuthClient,
  buildJwtAssertion,
  type SfdcOAuthCreds,
} from "../src/auth.js";

function makeLogger() {
  const sink = new PassThrough();
  sink.on("data", () => {});
  return {
    logger: getLogger({
      adapterName: "t",
      vendor: "salesforce_fsc",
      destination: sink,
      level: "error",
    }),
    sink,
  };
}

function fakeCreds(): SfdcOAuthCreds {
  const { privateKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    publicKeyEncoding: { type: "spki", format: "pem" },
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
  });
  return {
    clientId: "3MVGplaceholder",
    username: "svcacct@example.com.invalid",
    privateKeyPEM: privateKey,
    loginUrl: "https://test.salesforce.com",
  };
}

function stubFetch(opts: { status: number; body: string }): unknown {
  return async (_url: string) => ({
    statusCode: opts.status,
    headers: {},
    body: { text: async () => opts.body },
  });
}

describe("buildJwtAssertion", () => {
  it("emits a three-part base64url JWT", () => {
    const jwt = buildJwtAssertion(fakeCreds(), Date.now());
    const parts = jwt.split(".");
    expect(parts.length).toBe(3);
    for (const p of parts) {
      expect(p).toMatch(/^[A-Za-z0-9_-]+$/);
    }
  });
});

describe("SfdcAuthClient — acquire + SSRF + LRU", () => {
  const ALLOW = ["my.salesforce.com", "salesforce.com"] as const;

  it("caches token per firm (AC4.14)", async () => {
    const { logger } = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/salesforce_fsc/oauth_credentials": fakeCreds(),
    });
    const auth = new SfdcAuthClient({
      secrets,
      secretPath: "m11/salesforce_fsc/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      egressAllowlist: ALLOW,
      ssrfResolve: async () => ["52.1.1.1"],
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "synthetic_access_DONOTLEAK",
          instance_url: "https://acme.my.salesforce.com",
        }),
      }) as never,
    });
    const t1 = await auth.getToken("acme");
    const t2 = await auth.getToken("acme");
    expect(t1.accessToken).toBe(t2.accessToken);
    expect(auth.cacheSize()).toBe(1);
    await auth.getToken("bobco");
    expect(auth.cacheSize()).toBe(2);
  });

  it("AC14.10 — rejects instance_url pointing at 169.254.169.254", async () => {
    const { logger } = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/salesforce_fsc/oauth_credentials": fakeCreds(),
    });
    const auth = new SfdcAuthClient({
      secrets,
      secretPath: "m11/salesforce_fsc/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      egressAllowlist: ALLOW,
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "synthetic_access_DONOTLEAK",
          instance_url: "http://169.254.169.254/latest/meta-data/",
        }),
      }) as never,
    });
    await expect(auth.getToken("acme")).rejects.toThrow(AdapterError);
    try {
      await auth.getToken("acme");
    } catch (e) {
      expect((e as AdapterError).code).toBe("vendor_ssrf_blocked");
    }
  });

  it("AC4.5 — token never leaks into log stream", async () => {
    const sink = new PassThrough();
    let out = "";
    sink.on("data", (c) => (out += String(c)));
    const logger = getLogger({
      adapterName: "t",
      vendor: "salesforce_fsc",
      destination: sink,
    });
    const ACCESS = "token_placeholder_DONOTLEAK_zzz";
    const secrets = new FakeSecretsClient({
      "m11/salesforce_fsc/oauth_credentials": fakeCreds(),
    });
    const auth = new SfdcAuthClient({
      secrets,
      secretPath: "m11/salesforce_fsc/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      egressAllowlist: ALLOW,
      ssrfResolve: async () => ["52.1.1.1"],
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: ACCESS,
          instance_url: "https://acme.my.salesforce.com",
        }),
      }) as never,
    });
    await auth.getToken("acme");
    expect(out).not.toContain(ACCESS);
  });

  it("AC4.14 — LRU 1024 caps size", async () => {
    const { logger } = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/salesforce_fsc/oauth_credentials": fakeCreds(),
    });
    const auth = new SfdcAuthClient({
      secrets,
      secretPath: "m11/salesforce_fsc/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      egressAllowlist: ALLOW,
      ssrfResolve: async () => ["52.1.1.1"],
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "synthetic_access_DONOTLEAK",
          instance_url: "https://acme.my.salesforce.com",
        }),
      }) as never,
    });
    for (let i = 0; i < 1025; i++) {
      await auth.getToken(`firm-${i}`);
    }
    expect(auth.cacheSize()).toBeLessThanOrEqual(1024);
  });
});

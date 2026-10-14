import { describe, it, expect } from "vitest";
import { PassThrough } from "node:stream";

import {
  FakeClock,
  FakeSecretsClient,
  getLogger,
  AdapterError,
} from "@project-007/mcp-sdk";

import { OrionBasicStrategy, OrionOAuthStrategy } from "../src/auth.js";

function makeLogger() {
  const sink = new PassThrough();
  sink.on("data", () => {});
  return getLogger({ adapterName: "t", vendor: "orion", destination: sink, level: "error" });
}

function stubFetch(opts: { status: number; body: string }): unknown {
  return async () => ({
    statusCode: opts.status,
    headers: {},
    body: { text: async () => opts.body },
  });
}

describe("OrionOAuthStrategy — Phase 2", () => {
  it("caches token per firm + emits Bearer header", async () => {
    const logger = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/orion/oauth_credentials": {
        clientId: "cid",
        clientSecret: "cs_placeholder_DONOTLEAK",
        tokenUrl: "https://api.orionadvisor.com/oauth/token",
      },
    });
    const auth = new OrionOAuthStrategy({
      secrets,
      secretPath: "m11/orion/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      fetchImpl: stubFetch({
        status: 200,
        body: JSON.stringify({ access_token: "tok_placeholder_DONOTLEAK", expires_in: 3600 }),
      }) as never,
    });
    const h1 = await auth.headerFor("acme");
    const h2 = await auth.headerFor("acme");
    expect(h1.authorization).toBe(h2.authorization);
    expect(h1.authorization.startsWith("Bearer ")).toBe(true);
    expect(auth.cacheSize()).toBe(1);
    await auth.headerFor("bobco");
    expect(auth.cacheSize()).toBe(2);
  });

  it("throws vendor_auth_failed on non-200", async () => {
    const logger = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/orion/oauth_credentials": {
        clientId: "cid",
        clientSecret: "cs_placeholder_DONOTLEAK",
        tokenUrl: "https://api.orionadvisor.com/oauth/token",
      },
    });
    const auth = new OrionOAuthStrategy({
      secrets,
      secretPath: "m11/orion/oauth_credentials",
      clock: new FakeClock(0),
      logger,
      fetchImpl: stubFetch({ status: 401, body: "denied" }) as never,
    });
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });
});

describe("OrionBasicStrategy — Phase 3 toggle (AC4.12)", () => {
  it("loads once at init + emits Basic header", async () => {
    const logger = makeLogger();
    const secrets = new FakeSecretsClient({
      "m11/orion/basic_credentials": { username: "svc-acct", password: "placeholder_pw_DONOTLEAK" },
    });
    const auth = new OrionBasicStrategy({
      secrets,
      secretPath: "m11/orion/basic_credentials",
      logger,
    });
    await auth.init();
    const h = await auth.headerFor("acme");
    expect(h.authorization.startsWith("Basic ")).toBe(true);
    expect(auth.healthy()).toBe(true);
  });

  it("throws before init()", async () => {
    const logger = makeLogger();
    const auth = new OrionBasicStrategy({
      secrets: new FakeSecretsClient({}),
      secretPath: "m11/orion/basic_credentials",
      logger,
    });
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });
});

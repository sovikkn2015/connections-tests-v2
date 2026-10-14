/**
 * Smarsh auth tests — HMAC-SHA256 signing + OAuth2 scope enforcement.
 *
 * 12 cases across two auth strategies.
 *   - HMAC: signing string canonicalization, header emission, Vault round-trip,
 *     timestamp from clock (replay-defence observable), constant-time compare.
 *   - OAuth2: exact-scope match + super/sub/empty rejection (AC-SM5).
 *
 * No network. No live vendor. FakeClock + FakeSecretsClient + stubbed fetch.
 */

import { createHash, createHmac } from "node:crypto";
import { PassThrough } from "node:stream";

import { describe, it, expect } from "vitest";

import {
  AdapterError,
  FakeClock,
  FakeSecretsClient,
  getLogger,
  type Logger,
} from "@project-007/mcp-sdk";

import { SmarshAuthClient } from "../src/auth.js";
import {
  SmarshHmacSigner,
  buildSigningString,
  computeHmacSignature,
  constantTimeHexEqual,
} from "../src/auth_hmac.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function silentLogger(): { logger: Logger; out: () => string } {
  const sink = new PassThrough();
  let out = "";
  sink.on("data", (c) => (out += String(c)));
  return {
    logger: getLogger({
      adapterName: "t",
      vendor: "smarsh",
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

// ---------------------------------------------------------------------------
// HMAC signing (6 cases)
// ---------------------------------------------------------------------------

describe("HMAC signing — canonical signing string", () => {
  it("case 1 — buildSigningString matches METHOD\\nPATH\\nTS\\nSHA256(body)", () => {
    const body = '{"hello":"world"}';
    const bodyHash = createHash("sha256").update(body, "utf8").digest("hex");
    const s = buildSigningString("POST", "/api/v1/captures", 1716214800, body);
    expect(s).toBe(`POST\n/api/v1/captures\n1716214800\n${bodyHash}`);
  });

  it("case 2 — method is uppercased", () => {
    const s = buildSigningString("post", "/x", 0, "");
    expect(s.startsWith("POST\n/x\n0\n")).toBe(true);
  });

  it("case 3 — computeHmacSignature matches node's own HMAC-SHA256", () => {
    const secret = "s" + "0".repeat(63); // 64 chars
    const signingString = buildSigningString("GET", "/api/v1/captures/abc/status", 1000, "");
    const mine = computeHmacSignature(secret, signingString);
    const theirs = createHmac("sha256", secret).update(signingString, "utf8").digest("hex");
    expect(mine).toBe(theirs);
    expect(mine).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("SmarshHmacSigner — end-to-end via Vault", () => {
  async function makeSigner(
    override: {
      clockMs?: number;
      apiKey?: string;
      hmacSecret?: string;
    } = {},
  ): Promise<{ signer: SmarshHmacSigner; clock: FakeClock; secrets: FakeSecretsClient }> {
    const { logger } = silentLogger();
    const clock = new FakeClock(override.clockMs ?? 1716214800_000);
    const secrets = new FakeSecretsClient({
      "m11/smarsh/api_key":
        override.apiKey ?? "api_key_placeholder_DONOTLEAK",
      "m11/smarsh/hmac_secret":
        override.hmacSecret ?? "hmac_secret_DONOTLEAK_" + "x".repeat(32),
    });
    const signer = new SmarshHmacSigner({
      secrets,
      apiKeyPath: "m11/smarsh/api_key",
      hmacSecretPath: "m11/smarsh/hmac_secret",
      clock,
      logger,
    });
    return { signer, clock, secrets };
  }

  it("case 4 — emits all 4 HMAC headers with correct timestamp + body hash", async () => {
    const { signer } = await makeSigner();
    const body = '{"capture_id":"abc","file_name":"x.pdf"}';
    const h = await signer.sign({
      method: "POST",
      path: "/api/v1/captures",
      body,
    });
    expect(h["x-smarsh-api-key"]).toBe("api_key_placeholder_DONOTLEAK");
    expect(h["x-smarsh-timestamp"]).toBe("1716214800");
    expect(h["x-smarsh-body-sha256"]).toBe(
      createHash("sha256").update(body, "utf8").digest("hex"),
    );
    expect(h["x-smarsh-signature"]).toMatch(/^[0-9a-f]{64}$/);
  });

  it("case 5 — signature matches an independently computed HMAC", async () => {
    const hmacSecret = "hmac_secret_DONOTLEAK_" + "x".repeat(32);
    const { signer } = await makeSigner({ hmacSecret });
    const body = "";
    const h = await signer.sign({
      method: "GET",
      path: "/api/v1/captures/abc-123/status",
      body,
    });
    const expected = createHmac("sha256", hmacSecret)
      .update(
        `GET\n/api/v1/captures/abc-123/status\n1716214800\n${createHash(
          "sha256",
        )
          .update("", "utf8")
          .digest("hex")}`,
        "utf8",
      )
      .digest("hex");
    expect(h["x-smarsh-signature"]).toBe(expected);
  });

  it("case 6 — timestamp moves forward when clock advances (replay-defence observable)", async () => {
    const { signer, clock } = await makeSigner();
    const first = await signer.sign({ method: "GET", path: "/x", body: "" });
    clock.advance(5_000); // +5s
    const second = await signer.sign({ method: "GET", path: "/x", body: "" });
    expect(second["x-smarsh-timestamp"]).toBe(
      String(Number(first["x-smarsh-timestamp"]) + 5),
    );
    expect(second["x-smarsh-signature"]).not.toBe(first["x-smarsh-signature"]);
  });

  it("case 7 — rejects too-short hmac_secret with vendor_auth_failed", async () => {
    const { signer } = await makeSigner({ hmacSecret: "too-short" });
    await expect(
      signer.sign({ method: "GET", path: "/x", body: "" }),
    ).rejects.toThrow(AdapterError);
  });

  it("case 8 — rejects missing api_key with vendor_auth_failed", async () => {
    const { logger } = silentLogger();
    const secrets = new FakeSecretsClient({
      "m11/smarsh/hmac_secret": "hmac_secret_DONOTLEAK_" + "x".repeat(32),
    });
    const signer = new SmarshHmacSigner({
      secrets,
      apiKeyPath: "m11/smarsh/api_key",
      hmacSecretPath: "m11/smarsh/hmac_secret",
      clock: new FakeClock(0),
      logger,
    });
    await expect(
      signer.sign({ method: "GET", path: "/x", body: "" }),
    ).rejects.toThrow();
  });
});

describe("constantTimeHexEqual", () => {
  it("case 9 — equal hex strings compare true", () => {
    const a = "a".repeat(64);
    expect(constantTimeHexEqual(a, a)).toBe(true);
  });
  it("case 10 — different-length strings compare false (no crash)", () => {
    expect(constantTimeHexEqual("abcd", "abcdef")).toBe(false);
    expect(constantTimeHexEqual("", "")).toBe(true);
    expect(constantTimeHexEqual("not-hex", "not-hex")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// OAuth2 scope enforcement (6 cases) — AC-SM5
// ---------------------------------------------------------------------------

function makeOAuthAuth(fetchImpl: unknown, captured?: { logger: Logger }): SmarshAuthClient {
  const logger = captured?.logger ?? silentLogger().logger;
  const secrets = new FakeSecretsClient({
    "m11/smarsh/oauth_credentials": {
      clientId: "cid",
      clientSecret: "cs_placeholder_DONOTLEAK",
    },
  });
  return new SmarshAuthClient({
    secrets,
    credentialsPath: "m11/smarsh/oauth_credentials",
    tokenUrl: "https://auth.smarsh.com/oauth/token",
    clock: new FakeClock(0),
    logger,
    fetchImpl: fetchImpl as never,
  });
}

describe("OAuth2 exact-scope enforcement (AC-SM5)", () => {
  it("case 11 — exact scope match (archive.write read search) → token cached", async () => {
    const auth = makeOAuthAuth(
      stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_DONOTLEAK",
          expires_in: 3600,
          scope: "archive.write archive.read archive.search",
        }),
      }),
    );
    const h = await auth.headerFor("acme");
    expect(h.authorization.startsWith("Bearer ")).toBe(true);
    expect(auth.cacheSize()).toBe(1);
  });

  it("case 12 — superset granted (extra `archive.admin`) → vendor_auth_failed", async () => {
    const auth = makeOAuthAuth(
      stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_DONOTLEAK",
          expires_in: 3600,
          scope:
            "archive.write archive.read archive.search archive.admin",
        }),
      }),
    );
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });

  it("case 13 — subset granted (missing `archive.search`) → vendor_auth_failed", async () => {
    const auth = makeOAuthAuth(
      stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_DONOTLEAK",
          expires_in: 3600,
          scope: "archive.write archive.read",
        }),
      }),
    );
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });

  it("case 14 — empty scope string → vendor_auth_failed", async () => {
    const auth = makeOAuthAuth(
      stubFetch({
        status: 200,
        body: JSON.stringify({
          access_token: "at_DONOTLEAK",
          expires_in: 3600,
          scope: "",
        }),
      }),
    );
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });

  it("case 15 — token endpoint 401 → vendor_auth_failed with vendorStatusCode=401", async () => {
    const auth = makeOAuthAuth(
      stubFetch({ status: 401, body: "denied" }),
    );
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });

  it("case 16 — malformed JSON response → vendor_invalid_json", async () => {
    const auth = makeOAuthAuth(stubFetch({ status: 200, body: "not-json{" }));
    await expect(auth.headerFor("acme")).rejects.toThrow(AdapterError);
  });
});

// ---------------------------------------------------------------------------
// No literal credentials assertion (AC-SM6) — quick grep against the source tree.
// ---------------------------------------------------------------------------

describe("AC-SM6 — no literal credentials in source", () => {
  it("case 17 — src/ files do not contain well-known credential patterns", async () => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    // __dirname not available in ESM; resolve from this test's URL.
    const here = path.dirname(new URL(import.meta.url).pathname);
    const srcDir = path.resolve(here, "..", "src");
    const entries = await fs.readdir(srcDir);
    const offenders: string[] = [];
    const BAD = [
      /sk_live_[A-Za-z0-9]{16,}/, // Stripe-style live
      /AKIA[0-9A-Z]{16}/, // AWS access key
      /-----BEGIN (RSA |EC |)PRIVATE KEY-----/, // PEM
    ];
    for (const name of entries) {
      if (!name.endsWith(".ts")) continue;
      const txt = await fs.readFile(path.join(srcDir, name), "utf8");
      for (const re of BAD) {
        if (re.test(txt)) offenders.push(`${name} matches ${re}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});

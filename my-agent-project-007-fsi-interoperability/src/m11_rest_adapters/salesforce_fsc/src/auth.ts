/**
 * SFDC JWT-Bearer OAuth flow (AC4.1-AC4.14, AC14.10).
 *
 * Flow per Appendix C.1:
 *   1. Build RS256-signed JWT assertion.
 *   2. POST to {loginUrl}/services/oauth2/token.
 *   3. SSRF-validate response.instance_url against egress allow-list.
 *   4. Cache access token in LRU (max 1024) with expiresAt=now+7200s.
 *   5. On 401 during tool call: invalidate, retry once.
 */

import { createSign, randomBytes } from "node:crypto";
import { request } from "undici";

import {
  AdapterError,
  assertVendorURLSafe,
  type Clock,
  type Logger,
  LRUCache,
  type SecretsClient,
} from "@project-007/mcp-sdk";

export interface SfdcOAuthCreds {
  readonly clientId: string;
  readonly username: string;
  readonly privateKeyPEM: string;
  readonly loginUrl: string;
}

export interface CachedToken {
  readonly accessToken: string;
  readonly instanceUrl: string;
  readonly expiresAt: number;
}

export interface SfdcAuthOptions {
  readonly secrets: SecretsClient;
  readonly secretPath: string;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly egressAllowlist: readonly string[];
  readonly ssrfResolve?: (h: string) => Promise<string[]>;
  readonly fetchImpl?: typeof request;
}

const DEFAULT_TTL_MS = 7_200_000;
const PROACTIVE_REFRESH_MS = 60_000;

function b64urlEncode(data: string | Buffer): string {
  return (typeof data === "string" ? Buffer.from(data) : data)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export function buildJwtAssertion(
  creds: SfdcOAuthCreds,
  now: number,
): string {
  const header = { alg: "RS256", typ: "JWT" };
  const jti = b64urlEncode(randomBytes(8));
  const payload = {
    iss: creds.clientId,
    sub: creds.username,
    aud: creds.loginUrl,
    exp: Math.floor(now / 1000) + 300,
    jti,
  };
  const head = b64urlEncode(JSON.stringify(header));
  const body = b64urlEncode(JSON.stringify(payload));
  const signingInput = `${head}.${body}`;
  const sig = createSign("RSA-SHA256")
    .update(signingInput)
    .sign(creds.privateKeyPEM);
  return `${signingInput}.${b64urlEncode(sig)}`;
}

export class SfdcAuthClient {
  private readonly cache: LRUCache<string, CachedToken>;
  private readonly fetch: typeof request;
  private ssrfValidated: boolean = false;

  constructor(private readonly opts: SfdcAuthOptions) {
    this.cache = new LRUCache({ max: 1024, updateAgeOnGet: true });
    this.fetch = opts.fetchImpl ?? request;
  }

  cacheSize(): number {
    return this.cache.size;
  }

  invalidate(firmId: string): void {
    this.cache.delete(firmId);
  }

  async getToken(firmId: string): Promise<CachedToken> {
    const cached = this.cache.get(firmId);
    if (cached && cached.expiresAt - this.opts.clock.now() > PROACTIVE_REFRESH_MS) {
      return cached;
    }
    if (cached) {
      this.opts.logger.info({
        event: "auth.sfdc.refresh_proactive",
        firm_id: firmId,
      });
    }
    const fresh = await this.acquire(firmId);
    this.cache.set(firmId, fresh);
    return fresh;
  }

  private async acquire(firmId: string): Promise<CachedToken> {
    const creds = await this.opts.secrets.getJSONSecret<SfdcOAuthCreds>(
      this.opts.secretPath,
    );
    const assertion = buildJwtAssertion(creds, this.opts.clock.now());
    this.opts.logger.info({
      event: "auth.sfdc.jwt_assertion_built",
      firm_id: firmId,
    });

    const tokenUrl = `${creds.loginUrl.replace(/\/+$/, "")}/services/oauth2/token`;
    const body = new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }).toString();

    const res = await this.fetch(tokenUrl, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body,
    });
    const text = await res.body.text();
    if (res.statusCode !== 200) {
      throw new AdapterError(
        "vendor_auth_failed",
        `SFDC token endpoint returned ${res.statusCode}`,
        res.statusCode,
      );
    }
    let json: {
      access_token?: string;
      instance_url?: string;
    };
    try {
      json = JSON.parse(text);
    } catch {
      throw new AdapterError(
        "vendor_invalid_json",
        "SFDC token response was not valid JSON",
        200,
      );
    }
    if (!json.access_token || !json.instance_url) {
      throw new AdapterError(
        "vendor_auth_failed",
        "SFDC token response missing access_token / instance_url",
        200,
      );
    }

    await assertVendorURLSafe(
      json.instance_url,
      this.opts.egressAllowlist,
      this.opts.ssrfResolve ? { resolve: this.opts.ssrfResolve } : {},
    );
    this.opts.logger.info({
      event: "auth.sfdc.ssrf_check_passed",
      firm_id: firmId,
    });
    this.ssrfValidated = true;

    const token: CachedToken = {
      accessToken: json.access_token,
      instanceUrl: json.instance_url,
      expiresAt: this.opts.clock.now() + DEFAULT_TTL_MS,
    };
    this.opts.logger.info({
      event: "auth.sfdc.token_acquired",
      firm_id: firmId,
      ttl_ms: DEFAULT_TTL_MS,
    });
    return token;
  }

  healthy(): boolean {
    return this.ssrfValidated;
  }
}

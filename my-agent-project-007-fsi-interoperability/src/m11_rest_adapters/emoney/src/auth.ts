/** eMoney OAuth client_credentials + strict scope enforcement (Appendix C.3). */

import { request } from "undici";

import {
  AdapterError,
  type Clock,
  type Logger,
  LRUCache,
  type SecretsClient,
} from "@project-007/mcp-sdk";

export interface EMoneyCreds {
  readonly clientId: string;
  readonly clientSecret: string;
  readonly tokenUrl: string;
  readonly scope: string;
}

export interface CachedToken {
  readonly accessToken: string;
  readonly expiresAt: number;
  readonly grantedScope: string;
}

export interface EMoneyAuthOptions {
  readonly secrets: SecretsClient;
  readonly secretPath: string;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly requiredScope: string;
  readonly fetchImpl?: typeof request;
}

const DEFAULT_TTL_MS = 3_600_000;
const PROACTIVE_MS = 60_000;

export class EMoneyAuthClient {
  private readonly cache: LRUCache<string, CachedToken>;
  private readonly fetch: typeof request;
  private healthyFlag = false;

  constructor(private readonly opts: EMoneyAuthOptions) {
    this.cache = new LRUCache({ max: 1024, updateAgeOnGet: true });
    this.fetch = opts.fetchImpl ?? request;
  }

  healthy(): boolean {
    return this.healthyFlag;
  }

  async getToken(firmId: string): Promise<CachedToken> {
    const cached = this.cache.get(firmId);
    if (cached && cached.expiresAt - this.opts.clock.now() > PROACTIVE_MS) {
      return cached;
    }
    const creds = await this.opts.secrets.getJSONSecret<EMoneyCreds>(
      this.opts.secretPath,
    );
    const basic = Buffer.from(
      `${creds.clientId}:${creds.clientSecret}`,
      "utf8",
    ).toString("base64");
    const form = new URLSearchParams({
      grant_type: "client_credentials",
      scope: this.opts.requiredScope,
    }).toString();
    const res = await this.fetch(creds.tokenUrl, {
      method: "POST",
      headers: {
        authorization: `Basic ${basic}`,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: form,
    });
    const text = await res.body.text();
    if (res.statusCode !== 200) {
      throw new AdapterError(
        "vendor_auth_failed",
        `eMoney token endpoint returned ${res.statusCode}`,
        res.statusCode,
      );
    }
    let json: { access_token?: string; scope?: string; expires_in?: number };
    try {
      json = JSON.parse(text);
    } catch {
      throw new AdapterError(
        "vendor_invalid_json",
        "eMoney token response not JSON",
        200,
      );
    }
    if (!json.access_token) {
      throw new AdapterError(
        "vendor_auth_failed",
        "eMoney token response missing access_token",
        200,
      );
    }
    const granted = (json.scope ?? "").trim();
    if (granted !== this.opts.requiredScope) {
      this.opts.logger.fatal({
        event: "auth.emoney.scope_violation",
        requested: this.opts.requiredScope,
        granted,
        firm_id: firmId,
      });
      throw new AdapterError(
        "vendor_auth_failed",
        "eMoney granted scope does not match requested",
        200,
      );
    }
    const ttl = json.expires_in ? json.expires_in * 1000 : DEFAULT_TTL_MS;
    const tok: CachedToken = {
      accessToken: json.access_token,
      expiresAt: this.opts.clock.now() + ttl,
      grantedScope: granted,
    };
    this.cache.set(firmId, tok);
    this.healthyFlag = true;
    this.opts.logger.info({
      event: "auth.emoney.token_acquired",
      firm_id: firmId,
      ttl_ms: ttl,
    });
    return tok;
  }

  cacheSize(): number {
    return this.cache.size;
  }
}

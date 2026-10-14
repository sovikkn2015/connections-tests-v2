/**
 * Orion auth strategies. Spec AC4.12 — OAuth (Phase 2) + Basic (Phase 3).
 * Mode resolved at startup; not hot-reloadable.
 */

import { request } from "undici";

import {
  AdapterError,
  type Clock,
  type Logger,
  LRUCache,
  type SecretsClient,
} from "@project-007/mcp-sdk";

export interface BaseAuthStrategy {
  headerFor(firmId: string): Promise<{ authorization: string }>;
  healthy(): boolean;
}

export interface OrionOAuthCreds {
  readonly clientId: string;
  readonly clientSecret: string;
  readonly tokenUrl: string;
}

export interface OrionBasicCreds {
  readonly username: string;
  readonly password: string;
}

interface CachedOauthToken {
  readonly accessToken: string;
  readonly expiresAt: number;
}

export interface OrionOAuthOptions {
  readonly secrets: SecretsClient;
  readonly secretPath: string;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly fetchImpl?: typeof request;
}

const DEFAULT_TTL_MS = 3_600_000;
const PROACTIVE_MS = 60_000;

export class OrionOAuthStrategy implements BaseAuthStrategy {
  private readonly cache: LRUCache<string, CachedOauthToken>;
  private readonly fetch: typeof request;
  private bootstrappedOnce = false;

  constructor(private readonly opts: OrionOAuthOptions) {
    this.cache = new LRUCache({ max: 1024, updateAgeOnGet: true });
    this.fetch = opts.fetchImpl ?? request;
  }

  async headerFor(firmId: string): Promise<{ authorization: string }> {
    const tok = await this.getToken(firmId);
    return { authorization: `Bearer ${tok.accessToken}` };
  }

  healthy(): boolean {
    return this.bootstrappedOnce;
  }

  private async getToken(firmId: string): Promise<CachedOauthToken> {
    const cached = this.cache.get(firmId);
    if (cached && cached.expiresAt - this.opts.clock.now() > PROACTIVE_MS) {
      return cached;
    }
    const creds = await this.opts.secrets.getJSONSecret<OrionOAuthCreds>(
      this.opts.secretPath,
    );
    const basic = Buffer.from(
      `${creds.clientId}:${creds.clientSecret}`,
      "utf8",
    ).toString("base64");
    const res = await this.fetch(creds.tokenUrl, {
      method: "POST",
      headers: {
        authorization: `Basic ${basic}`,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: "grant_type=client_credentials",
    });
    const text = await res.body.text();
    if (res.statusCode !== 200) {
      throw new AdapterError(
        "vendor_auth_failed",
        `Orion token endpoint returned ${res.statusCode}`,
        res.statusCode,
      );
    }
    let json: { access_token?: string; expires_in?: number };
    try {
      json = JSON.parse(text);
    } catch {
      throw new AdapterError(
        "vendor_invalid_json",
        "Orion token response not JSON",
        200,
      );
    }
    if (!json.access_token) {
      throw new AdapterError(
        "vendor_auth_failed",
        "Orion token response missing access_token",
        200,
      );
    }
    const ttl = json.expires_in ? json.expires_in * 1000 : DEFAULT_TTL_MS;
    const tok = {
      accessToken: json.access_token,
      expiresAt: this.opts.clock.now() + ttl,
    };
    this.cache.set(firmId, tok);
    this.bootstrappedOnce = true;
    this.opts.logger.info({
      event: "auth.orion.token_acquired",
      firm_id: firmId,
      ttl_ms: ttl,
    });
    return tok;
  }

  cacheSize(): number {
    return this.cache.size;
  }

  invalidate(firmId: string): void {
    this.cache.delete(firmId);
  }
}

export interface OrionBasicOptions {
  readonly secrets: SecretsClient;
  readonly secretPath: string;
  readonly logger: Logger;
}

/** Static Basic auth loaded once at startup (AC4.12 — pod redeploy to change). */
export class OrionBasicStrategy implements BaseAuthStrategy {
  private header: string | null = null;
  private ready = false;

  constructor(private readonly opts: OrionBasicOptions) {}

  async init(): Promise<void> {
    const creds = await this.opts.secrets.getJSONSecret<OrionBasicCreds>(
      this.opts.secretPath,
    );
    const b = Buffer.from(
      `${creds.username}:${creds.password}`,
      "utf8",
    ).toString("base64");
    this.header = `Basic ${b}`;
    this.ready = true;
    this.opts.logger.info({ event: "auth.orion.basic_loaded" });
  }

  async headerFor(_firmId: string): Promise<{ authorization: string }> {
    if (!this.header) {
      throw new AdapterError(
        "vendor_auth_failed",
        "Orion basic auth not initialised",
        null,
      );
    }
    return { authorization: this.header };
  }

  healthy(): boolean {
    return this.ready;
  }
}

/**
 * Schwab OAuth refresh-token rotation flow. Spec AC4.7 + AC4.13 + AC4.14.
 *
 * On every refresh, Schwab returns a NEW refresh token. Adapter writes it
 * back to Secrets (resourceName-scoped RBAC per §RBAC Template).
 *
 * setSecret failure → pino.fatal event auth.schwab.rt_rotation_failed with
 * severity:"CRITICAL" → M10 sidecar → PagerDuty within 5 min.
 * Adapter does NOT crash — access token still valid.
 */

import { request } from "undici";

import {
  AdapterError,
  type Clock,
  type Logger,
  LRUCache,
  type SecretsClient,
} from "@project-007/mcp-sdk";

export interface SchwabOAuthCreds {
  readonly clientId: string;
  readonly clientSecret: string;
}

export interface CachedAccess {
  readonly accessToken: string;
  readonly expiresAt: number;
}

export interface SchwabAuthOptions {
  readonly secrets: SecretsClient;
  readonly credentialsPath: string;
  readonly refreshTokenPath: string;
  readonly tokenUrl: string;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly fetchImpl?: typeof request;
}

const DEFAULT_ACCESS_TTL_MS = 1_800_000; // 30 min
const PROACTIVE_MS = 60_000;

export class SchwabAuthClient {
  private readonly cache: LRUCache<string, CachedAccess>;
  private readonly fetch: typeof request;
  private rotationInFlight: Promise<unknown> | null = null;
  private healthyFlag = false;
  private oauthDegradedFirmIds: Set<string> = new Set();

  constructor(private readonly opts: SchwabAuthOptions) {
    this.cache = new LRUCache({ max: 1024, updateAgeOnGet: true });
    this.fetch = opts.fetchImpl ?? request;
  }

  healthy(): boolean {
    return this.healthyFlag && this.oauthDegradedFirmIds.size === 0;
  }

  /** SIGTERM handler — AC17.3 v0.2.0. */
  async waitForRotation(timeoutMs: number = 10_000): Promise<void> {
    if (!this.rotationInFlight) return;
    await Promise.race([
      this.rotationInFlight,
      new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
    ]);
  }

  async getToken(firmId: string): Promise<CachedAccess> {
    const cached = this.cache.get(firmId);
    if (cached && cached.expiresAt - this.opts.clock.now() > PROACTIVE_MS) {
      return cached;
    }
    const p = this.refresh(firmId);
    this.rotationInFlight = p;
    try {
      return await p;
    } finally {
      this.rotationInFlight = null;
    }
  }

  private async refresh(firmId: string): Promise<CachedAccess> {
    const creds = await this.opts.secrets.getJSONSecret<SchwabOAuthCreds>(
      this.opts.credentialsPath,
    );
    const currentRt = await this.opts.secrets.getSecret(
      this.opts.refreshTokenPath,
    );
    const basic = Buffer.from(
      `${creds.clientId}:${creds.clientSecret}`,
      "utf8",
    ).toString("base64");
    const form = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: currentRt,
    }).toString();

    const res = await this.fetch(this.opts.tokenUrl, {
      method: "POST",
      headers: {
        authorization: `Basic ${basic}`,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: form,
    });
    const text = await res.body.text();
    if (res.statusCode !== 200) {
      if (res.statusCode === 400) {
        this.opts.logger.fatal({
          event: "auth.schwab.rt_invalid_grant",
          firm_id: firmId,
          severity: "CRITICAL",
        });
      }
      throw new AdapterError(
        "vendor_auth_failed",
        `Schwab token endpoint returned ${res.statusCode}`,
        res.statusCode,
      );
    }
    let json: {
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
    };
    try {
      json = JSON.parse(text);
    } catch {
      throw new AdapterError(
        "vendor_invalid_json",
        "Schwab token response not JSON",
        200,
      );
    }
    if (!json.access_token || !json.refresh_token) {
      throw new AdapterError(
        "vendor_auth_failed",
        "Schwab token response missing access_token or refresh_token",
        200,
      );
    }

    // Persist new RT — AC4.13 CRITICAL alerting on failure.
    try {
      await this.opts.secrets.setSecret(
        this.opts.refreshTokenPath,
        json.refresh_token,
      );
      this.opts.logger.info({ event: "auth.schwab.rt_rotated", firm_id: firmId });
      this.oauthDegradedFirmIds.delete(firmId);
    } catch (err) {
      this.opts.logger.fatal({
        event: "auth.schwab.rt_rotation_failed",
        severity: "CRITICAL",
        firm_id: firmId,
        adapter: "schwab",
        retry_count: 0,
        reason: err instanceof Error ? err.message : "unknown",
      });
      this.oauthDegradedFirmIds.add(firmId);
      // Access token is still valid ~30 min; do NOT crash.
    }

    const ttl = json.expires_in ? json.expires_in * 1000 : DEFAULT_ACCESS_TTL_MS;
    const tok: CachedAccess = {
      accessToken: json.access_token,
      expiresAt: this.opts.clock.now() + ttl,
    };
    this.cache.set(firmId, tok);
    this.healthyFlag = true;
    return tok;
  }

  invalidate(firmId: string): void {
    this.cache.delete(firmId);
  }
  cacheSize(): number {
    return this.cache.size;
  }
}

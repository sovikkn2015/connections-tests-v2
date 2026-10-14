/**
 * Smarsh OAuth2 client_credentials flow with exact-match scope enforcement.
 * Spec §7 + AC-SM5.
 *
 * Smarsh issues short-lived bearer tokens (no refresh-token rotation like Schwab).
 * Per-firm token cache LRU 1024. Proactive refresh 60s before expiry.
 *
 * S1 — granted scope MUST be the exact set `archive.write archive.read archive.search`.
 * Superset granted → refuse (over-privilege). Subset → refuse (under-privilege). Empty → refuse.
 */

import { request } from "undici";

import {
  AdapterError,
  type Clock,
  type Logger,
  LRUCache,
  type SecretsClient,
} from "@project-007/mcp-sdk";

import { REQUIRED_SCOPES } from "./config.js";

export interface SmarshOAuthCreds {
  readonly clientId: string;
  readonly clientSecret: string;
  /** Optional override; falls back to config.oauthTokenUrl if absent in the vault blob. */
  readonly tokenUrl?: string;
}

export interface CachedAccess {
  readonly accessToken: string;
  readonly expiresAt: number;
}

export interface SmarshAuthOptions {
  readonly secrets: SecretsClient;
  readonly credentialsPath: string;
  readonly tokenUrl: string;
  readonly clock: Clock;
  readonly logger: Logger;
  readonly fetchImpl?: typeof request;
}

const DEFAULT_ACCESS_TTL_MS = 3_600_000; // 1h fallback when `expires_in` omitted
const PROACTIVE_MS = 60_000;

/** Parse the OAuth `scope` response into a deduped set. Tolerant of multi-space separators. */
function parseScopeResponse(raw: unknown): Set<string> | null {
  if (typeof raw !== "string" || raw.trim().length === 0) return null;
  return new Set(raw.split(/\s+/).filter((s) => s.length > 0));
}

/** Exact set equality check — same size + every member present. */
function setsEqual<T>(a: ReadonlySet<T>, b: ReadonlySet<T>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

export class SmarshAuthClient {
  private readonly cache: LRUCache<string, CachedAccess>;
  private readonly fetch: typeof request;
  private bootstrappedOnce = false;

  constructor(private readonly opts: SmarshAuthOptions) {
    this.cache = new LRUCache({ max: 1024, updateAgeOnGet: true });
    this.fetch = opts.fetchImpl ?? request;
  }

  healthy(): boolean {
    return this.bootstrappedOnce;
  }

  async headerFor(firmId: string): Promise<{ authorization: string }> {
    const tok = await this.getToken(firmId);
    return { authorization: `Bearer ${tok.accessToken}` };
  }

  async getToken(firmId: string): Promise<CachedAccess> {
    const cached = this.cache.get(firmId);
    if (cached && cached.expiresAt - this.opts.clock.now() > PROACTIVE_MS) {
      return cached;
    }
    return this.refresh(firmId);
  }

  /** Force re-acquisition (used on 401 from vendor call — retry once). */
  invalidate(firmId: string): void {
    this.cache.delete(firmId);
  }

  cacheSize(): number {
    return this.cache.size;
  }

  private async refresh(firmId: string): Promise<CachedAccess> {
    const creds = await this.opts.secrets.getJSONSecret<SmarshOAuthCreds>(
      this.opts.credentialsPath,
    );
    const url = creds.tokenUrl ?? this.opts.tokenUrl;
    const basic = Buffer.from(
      `${creds.clientId}:${creds.clientSecret}`,
      "utf8",
    ).toString("base64");
    const form = new URLSearchParams({
      grant_type: "client_credentials",
      scope: Array.from(REQUIRED_SCOPES).join(" "),
    }).toString();

    const res = await this.fetch(url, {
      method: "POST",
      headers: {
        authorization: `Basic ${basic}`,
        "content-type": "application/x-www-form-urlencoded",
        accept: "application/json",
      },
      body: form,
    });
    const text = await res.body.text();
    if (res.statusCode !== 200) {
      throw new AdapterError(
        "vendor_auth_failed",
        `Smarsh token endpoint returned ${res.statusCode}`,
        res.statusCode,
      );
    }
    let json: {
      access_token?: string;
      expires_in?: number;
      scope?: unknown;
      token_type?: string;
    };
    try {
      json = JSON.parse(text);
    } catch {
      throw new AdapterError(
        "vendor_invalid_json",
        "Smarsh token response not JSON",
        200,
      );
    }
    if (!json.access_token || typeof json.access_token !== "string") {
      throw new AdapterError(
        "vendor_auth_failed",
        "Smarsh token response missing access_token",
        200,
      );
    }

    // S1 — exact-match scope enforcement.
    const granted = parseScopeResponse(json.scope);
    if (!granted) {
      this.opts.logger.fatal({
        event: "auth.smarsh.scope_missing",
        severity: "CRITICAL",
        firm_id: firmId,
        reason: "empty_or_non_string",
      });
      throw new AdapterError(
        "vendor_auth_failed",
        "Smarsh token response has empty/non-string scope",
        200,
      );
    }
    if (!setsEqual(granted, REQUIRED_SCOPES)) {
      const grantedArr = Array.from(granted).sort();
      const requiredArr = Array.from(REQUIRED_SCOPES).sort();
      const reason =
        granted.size > REQUIRED_SCOPES.size
          ? "scope_superset_refused"
          : "missing_scope";
      this.opts.logger.fatal({
        event: "auth.smarsh.scope_mismatch",
        severity: "CRITICAL",
        firm_id: firmId,
        reason,
        granted_count: grantedArr.length,
        required_count: requiredArr.length,
      });
      throw new AdapterError(
        "vendor_auth_failed",
        `Smarsh granted scope does not exact-match required (${reason})`,
        200,
      );
    }

    const ttl = json.expires_in ? json.expires_in * 1000 : DEFAULT_ACCESS_TTL_MS;
    const tok: CachedAccess = {
      accessToken: json.access_token,
      expiresAt: this.opts.clock.now() + ttl,
    };
    this.cache.set(firmId, tok);
    this.bootstrappedOnce = true;
    this.opts.logger.info({
      event: "auth.smarsh.token_acquired",
      firm_id: firmId,
      ttl_ms: ttl,
    });
    return tok;
  }
}

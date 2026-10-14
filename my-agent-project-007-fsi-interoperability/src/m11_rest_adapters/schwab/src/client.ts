/** Schwab vendor client — 3 read-only tools. */

import {
  AdapterError,
  type Logger,
  type VendorHttpClient,
} from "@project-007/mcp-sdk";

import type { SchwabAuthClient } from "./auth.js";
import type {
  FetchMasterAccountArgs,
  FetchPositionsArgs,
  FetchTaxlotsArgs,
} from "./schemas.js";

export interface SchwabClientOptions {
  readonly auth: SchwabAuthClient;
  readonly http: VendorHttpClient;
  readonly logger: Logger;
  readonly apiBaseUrl: string;
  readonly vendorApiVersion: string;
}

function safeJson(txt: string): unknown {
  try {
    return JSON.parse(txt);
  } catch {
    throw new AdapterError(
      "vendor_invalid_json",
      "Schwab returned malformed JSON",
      null,
    );
  }
}

export class SchwabClient {
  constructor(private readonly opts: SchwabClientOptions) {}

  private async headers(firmId: string): Promise<Record<string, string>> {
    const tok = await this.opts.auth.getToken(firmId);
    return { authorization: `Bearer ${tok.accessToken}`, accept: "application/json" };
  }

  async fetchPositions(args: FetchPositionsArgs, firmId: string): Promise<unknown> {
    const v = this.opts.vendorApiVersion;
    const fields = args.fields?.join(",") ?? "positions";
    const url = `${this.opts.apiBaseUrl}/trader/${v}/accounts/${args.accountNumber}?fields=${encodeURIComponent(fields)}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers: await this.headers(firmId),
      toolName: "schwab.fetch_positions",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async fetchTaxlots(args: FetchTaxlotsArgs, firmId: string): Promise<unknown> {
    const v = this.opts.vendorApiVersion;
    const qs = args.symbol ? `?symbol=${encodeURIComponent(args.symbol)}` : "";
    const url = `${this.opts.apiBaseUrl}/trader/${v}/accounts/${args.accountNumber}/taxlots${qs}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers: await this.headers(firmId),
      toolName: "schwab.fetch_taxlots",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async fetchMasterAccount(
    args: FetchMasterAccountArgs,
    firmId: string,
  ): Promise<unknown> {
    const v = this.opts.vendorApiVersion;
    const qs = args.includeLinkedAccounts ? "?includeLinkedAccounts=true" : "";
    const url = `${this.opts.apiBaseUrl}/trader/${v}/masterAccounts/${args.masterAccountId}${qs}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers: await this.headers(firmId),
      toolName: "schwab.fetch_master_account",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async checkVersionAvailable(firmId: string): Promise<boolean> {
    const v = this.opts.vendorApiVersion;
    const url = `${this.opts.apiBaseUrl}/trader/${v}/userPreference`;
    try {
      const res = await this.opts.http.call({
        method: "GET",
        url,
        headers: await this.headers(firmId),
        toolName: "schwab.version_check",
        firmId,
      });
      return res.status < 400;
    } catch (err) {
      if (err instanceof AdapterError && err.code === "vendor_not_found") {
        this.opts.logger.fatal({
          event: "startup.schwab.version_404",
          severity: "CRITICAL",
          url,
        });
        return false;
      }
      throw err;
    }
  }
}

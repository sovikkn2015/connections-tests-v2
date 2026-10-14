/** Orion vendor client — 4 tool handlers. Paths PENDING-VERIFICATION per AC2.11. */

import {
  AdapterError,
  type Logger,
  type VendorHttpClient,
} from "@project-007/mcp-sdk";

import type { BaseAuthStrategy } from "./auth.js";
import type {
  FetchHoldingsArgs,
  FetchTransactionsArgs,
  FetchHouseholdArgs,
  FetchTaxlotsArgs,
} from "./schemas.js";

export interface OrionClientOptions {
  readonly auth: BaseAuthStrategy;
  readonly http: VendorHttpClient;
  readonly logger: Logger;
  readonly apiBaseUrl: string;
}

function safeJson(txt: string): unknown {
  try {
    return JSON.parse(txt);
  } catch {
    throw new AdapterError(
      "vendor_invalid_json",
      "Orion returned malformed JSON",
      null,
    );
  }
}

export class OrionClient {
  constructor(private readonly opts: OrionClientOptions) {}

  private async authedHeaders(firmId: string): Promise<Record<string, string>> {
    const h = await this.opts.auth.headerFor(firmId);
    return { ...h, accept: "application/json" };
  }

  async fetchHoldings(args: FetchHoldingsArgs, firmId: string): Promise<unknown> {
    const url =
      `${this.opts.apiBaseUrl}/api/v2.0/portfolio/accounts/${args.accountId}/positions` +
      (args.asOfDate ? `?asOfDate=${args.asOfDate}` : "");
    const headers = await this.authedHeaders(firmId);
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "orion.fetch_holdings",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async fetchTransactions(
    args: FetchTransactionsArgs,
    firmId: string,
  ): Promise<unknown> {
    const qs = `startDate=${args.startDate}&endDate=${args.endDate}`;
    const url = `${this.opts.apiBaseUrl}/api/v2.0/portfolio/accounts/${args.accountId}/transactions?${qs}`;
    const headers = await this.authedHeaders(firmId);
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "orion.fetch_transactions",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async fetchHousehold(args: FetchHouseholdArgs, firmId: string): Promise<unknown> {
    const url = `${this.opts.apiBaseUrl}/api/v2.0/portfolio/households/${args.householdId}`;
    const headers = await this.authedHeaders(firmId);
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "orion.fetch_household",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async fetchTaxlots(args: FetchTaxlotsArgs, firmId: string): Promise<unknown> {
    const url =
      `${this.opts.apiBaseUrl}/api/v2.0/portfolio/accounts/${args.accountId}/taxlots` +
      (args.asOfDate ? `?asOfDate=${args.asOfDate}` : "");
    const headers = await this.authedHeaders(firmId);
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "orion.fetch_taxlots",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  async probeBasePath(firmId: string): Promise<boolean> {
    const url = `${this.opts.apiBaseUrl}/api/v2.0/portfolio/accounts/1/positions`;
    const headers = await this.authedHeaders(firmId);
    try {
      await this.opts.http.call({
        method: "GET",
        url,
        headers,
        toolName: "orion.path_probe",
        firmId,
      });
      return true;
    } catch (err) {
      if (err instanceof AdapterError && err.code === "vendor_not_found") {
        this.opts.logger.warn({
          event: "orion.path_unverified",
          url,
          status: err.vendorStatusCode,
        });
        return false;
      }
      return true;
    }
  }
}

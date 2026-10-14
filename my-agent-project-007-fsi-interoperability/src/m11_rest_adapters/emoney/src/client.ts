import {
  AdapterError,
  type Logger,
  type VendorHttpClient,
} from "@project-007/mcp-sdk";

import type { EMoneyAuthClient } from "./auth.js";
import {
  EMoneyPlanSummaryOutput,
  type FetchPlanSummaryArgs,
} from "./schemas.js";

export interface EMoneyClientOptions {
  readonly auth: EMoneyAuthClient;
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
      "eMoney returned malformed JSON",
      null,
    );
  }
}

export class EMoneyClient {
  constructor(private readonly opts: EMoneyClientOptions) {}

  async fetchPlanSummary(
    args: FetchPlanSummaryArgs,
    firmId: string,
  ): Promise<unknown> {
    const tok = await this.opts.auth.getToken(firmId);
    const includeGoals = args.includeGoals ?? true;
    const url = `${this.opts.apiBaseUrl}/api/${this.opts.vendorApiVersion}/plans/${args.planId}/summary?includeGoals=${includeGoals}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers: {
        authorization: `Bearer ${tok.accessToken}`,
        accept: "application/json",
      },
      toolName: "emoney.fetch_plan_summary",
      firmId,
    });
    const body = safeJson(res.bodyText);
    const parsed = EMoneyPlanSummaryOutput.safeParse(body);
    if (!parsed.success) {
      const forbiddenKeys: string[] = [];
      for (const issue of parsed.error.issues) {
        if (issue.code === "unrecognized_keys") {
          for (const k of (issue as { keys: string[] }).keys) {
            forbiddenKeys.push(k);
          }
        }
      }
      this.opts.logger.warn({
        event: "emoney.raw_plan_rejected",
        firm_id: firmId,
        field_names: forbiddenKeys,
      });
      throw new AdapterError(
        "emoney_raw_plan_forbidden",
        "eMoney response contained non-summary fields; adapter configured SUMMARY-only",
        200,
      );
    }
    return parsed.data;
  }
}

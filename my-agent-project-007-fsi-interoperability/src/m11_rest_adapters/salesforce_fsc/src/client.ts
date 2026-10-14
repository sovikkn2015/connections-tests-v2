/**
 * SFDC vendor HTTP client — 5 tool handlers. Spec T-SF1..T-SF5.
 *
 * All responses are returned RAW (AC12.1). ETag captured as `_etag` sibling
 * on fetch_client so M6 can chain writebacks with `If-Match` (AC8.9).
 */

import {
  AdapterError,
  type Logger,
  type VendorHttpClient,
} from "@project-007/mcp-sdk";

import type { SfdcAuthClient } from "./auth.js";
import type {
  CreateInteractionSummaryArgs,
  FetchClientArgs,
  FetchGoalArgs,
  FetchHouseholdArgs,
  UpdateClientArgs,
} from "./schemas.js";

export interface SfdcClientOptions {
  readonly auth: SfdcAuthClient;
  readonly http: VendorHttpClient;
  readonly logger: Logger;
  readonly vendorApiVersion: string;
}

function safeJson<T = unknown>(txt: string): T {
  try {
    return JSON.parse(txt) as T;
  } catch {
    throw new AdapterError(
      "vendor_invalid_json",
      "SFDC returned malformed JSON",
      null,
    );
  }
}

async function buildHeaders(
  auth: SfdcAuthClient,
  firmId: string,
): Promise<{ headers: Record<string, string>; instanceUrl: string }> {
  const tok = await auth.getToken(firmId);
  return {
    headers: {
      authorization: `Bearer ${tok.accessToken}`,
      accept: "application/json",
      "content-type": "application/json",
    },
    instanceUrl: tok.instanceUrl.replace(/\/+$/, ""),
  };
}

export class SfdcClient {
  constructor(private readonly opts: SfdcClientOptions) {}

  async fetchClient(args: FetchClientArgs, firmId: string): Promise<unknown> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const v = this.opts.vendorApiVersion;
    const soql = `SELECT Id, Name, RecordType.Name, OwnerId, CreatedDate, LastModifiedDate, FinServ__FirmId__c, FinServ__HouseholdId__c, FinServ__ClientArchetype__c, FinServ__Jurisdiction__c, FinServ__KYCStatus__c, FinServ__KYCLastCompleted__c FROM Account WHERE Id = '${args.clientId}' LIMIT 1`;
    const url = `${instanceUrl}/services/data/${v}/query/?q=${encodeURIComponent(soql)}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "sfdc.fetch_client",
      firmId,
    });
    const body = safeJson<{ totalSize?: number; records?: unknown[] }>(
      res.bodyText,
    );
    if (!body.records || body.records.length === 0) {
      throw new AdapterError(
        "vendor_not_found",
        `SFDC account ${args.clientId} not found`,
        404,
      );
    }
    const etag = res.headers["etag"] ?? null;
    const record = body.records[0] as Record<string, unknown>;
    return etag ? { ...record, _etag: etag } : record;
  }

  async fetchHousehold(
    args: FetchHouseholdArgs,
    firmId: string,
  ): Promise<unknown> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const v = this.opts.vendorApiVersion;
    const soql = `SELECT Id, Name, OwnerId, CreatedDate, LastModifiedDate, (SELECT Id, FinServ__Account__c, FinServ__Role__c FROM FinServ__HouseholdMember__r) FROM FinServ__Household__c WHERE Id = '${args.householdId}' LIMIT 1`;
    const url = `${instanceUrl}/services/data/${v}/query/?q=${encodeURIComponent(soql)}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "sfdc.fetch_household",
      firmId,
    });
    const body = safeJson<{ records?: unknown[] }>(res.bodyText);
    if (!body.records || body.records.length === 0) {
      throw new AdapterError(
        "vendor_not_found",
        `SFDC household ${args.householdId} not found`,
        404,
      );
    }
    return body.records[0];
  }

  async fetchGoal(args: FetchGoalArgs, firmId: string): Promise<unknown> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const v = this.opts.vendorApiVersion;
    const soql = `SELECT Id, Name, FinServ__GoalType__c, FinServ__TargetAmount__c, FinServ__TargetDate__c, FinServ__Priority__c, FinServ__Status__c, CreatedDate, LastModifiedDate FROM FinServ__FinancialGoal__c WHERE Id = '${args.goalId}' LIMIT 1`;
    const url = `${instanceUrl}/services/data/${v}/query/?q=${encodeURIComponent(soql)}`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "sfdc.fetch_goal",
      firmId,
    });
    const body = safeJson<{ records?: unknown[] }>(res.bodyText);
    if (!body.records || body.records.length === 0) {
      throw new AdapterError(
        "vendor_not_found",
        `SFDC goal ${args.goalId} not found`,
        404,
      );
    }
    return body.records[0];
  }

  async updateClient(args: UpdateClientArgs, firmId: string): Promise<unknown> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const v = this.opts.vendorApiVersion;
    const url = `${instanceUrl}/services/data/${v}/sobjects/Account/${args.clientId}`;
    const res = await this.opts.http.call({
      method: "PATCH",
      url,
      headers: { ...headers, "if-match": args.ifMatch },
      body: JSON.stringify(args.fields),
      toolName: "sfdc.update_client",
      firmId,
    });
    if (res.status === 204) {
      return { updated: true, clientId: args.clientId };
    }
    return safeJson(res.bodyText);
  }

  async createInteractionSummary(
    args: CreateInteractionSummaryArgs,
    firmId: string,
  ): Promise<unknown> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const v = this.opts.vendorApiVersion;
    const url = `${instanceUrl}/services/data/${v}/sobjects/FinServ__Interaction__c`;
    const body: Record<string, unknown> = {
      FinServ__Client__c: args.clientId,
      FinServ__Summary__c: args.summaryText,
      FinServ__InteractionDate__c: args.interactionDate,
    };
    if (args.interactionType) {
      body.FinServ__InteractionType__c = args.interactionType;
    }
    const res = await this.opts.http.call({
      method: "POST",
      url,
      headers: { ...headers, "if-match": args.ifMatch },
      body: JSON.stringify(body),
      toolName: "sfdc.create_interaction_summary",
      firmId,
    });
    return safeJson(res.bodyText);
  }

  /** SFDC version check — hits GET /services/data/ (AC10.2). */
  async checkVersionAvailable(firmId: string): Promise<boolean> {
    const { headers, instanceUrl } = await buildHeaders(this.opts.auth, firmId);
    const url = `${instanceUrl}/services/data/`;
    const res = await this.opts.http.call({
      method: "GET",
      url,
      headers,
      toolName: "sfdc.version_check",
      firmId,
    });
    const versions = safeJson<Array<{ version?: string }>>(res.bodyText);
    return Array.isArray(versions)
      ? versions.some((v) => v.version === this.opts.vendorApiVersion)
      : false;
  }
}

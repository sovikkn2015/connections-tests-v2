/**
 * SFDC frozen tool registry (AC2.1, AC2.6, AC2.7, AC2.8).
 */

import type { ToolDefinition } from "@project-007/mcp-sdk";

import type { SfdcClient } from "./client.js";
import {
  CreateInteractionSummaryInput,
  FetchClientInput,
  FetchGoalInput,
  FetchHouseholdInput,
  UpdateClientInput,
} from "./schemas.js";

export function buildTools(
  client: SfdcClient,
): Readonly<Record<string, ToolDefinition>> {
  const tools: Record<string, ToolDefinition> = {
    "sfdc.fetch_client": {
      name: "sfdc.fetch_client",
      description:
        "Fetch a Salesforce FSC Account + Contact by Id — returns raw vendor JSON — use M7 translator to canonicalize. Captures ETag as `_etag` sibling for writeback idempotency.",
      input: FetchClientInput,
      handler: (args, ctx) =>
        client.fetchClient(args as never, ctx.firmId),
    },
    "sfdc.fetch_household": {
      name: "sfdc.fetch_household",
      description:
        "Fetch a Salesforce FSC Household with members — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchHouseholdInput,
      handler: (args, ctx) =>
        client.fetchHousehold(args as never, ctx.firmId),
    },
    "sfdc.fetch_goal": {
      name: "sfdc.fetch_goal",
      description:
        "Fetch a Salesforce FSC FinancialGoal by Id — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchGoalInput,
      handler: (args, ctx) =>
        client.fetchGoal(args as never, ctx.firmId),
    },
    "sfdc.update_client": {
      name: "sfdc.update_client",
      description:
        "Update an SFDC Account's non-PII fields via PATCH + If-Match. 412 → 409 vendor_conflict for M6 re-fetch + retry. PII fields are not writable (stay in SFDC UI).",
      input: UpdateClientInput,
      handler: (args, ctx) =>
        client.updateClient(args as never, ctx.firmId),
    },
    "sfdc.create_interaction_summary": {
      name: "sfdc.create_interaction_summary",
      description:
        "Create an FSC Interaction record with summary text + If-Match on the parent Account ETag. 412 → 409 vendor_conflict.",
      input: CreateInteractionSummaryInput,
      handler: (args, ctx) =>
        client.createInteractionSummary(args as never, ctx.firmId),
    },
  };
  return Object.freeze(tools);
}

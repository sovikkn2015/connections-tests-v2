import type { ToolDefinition } from "@project-007/mcp-sdk";

import type { EMoneyClient } from "./client.js";
import { FetchPlanSummaryInput } from "./schemas.js";

export function buildTools(
  client: EMoneyClient,
): Readonly<Record<string, ToolDefinition>> {
  return Object.freeze({
    "emoney.fetch_plan_summary": {
      name: "emoney.fetch_plan_summary",
      description:
        "Fetch eMoney plan SUMMARY (strict M7-aligned allow-list — 7 required + 14 optional fields). Any non-summary field triggers emoney_raw_plan_forbidden. Raw plan body never crosses the adapter boundary.",
      input: FetchPlanSummaryInput,
      handler: (args, ctx) =>
        client.fetchPlanSummary(args as never, ctx.firmId),
    },
  });
}

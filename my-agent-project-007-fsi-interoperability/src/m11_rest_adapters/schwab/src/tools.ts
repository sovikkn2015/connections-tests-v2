import type { ToolDefinition } from "@project-007/mcp-sdk";

import type { SchwabClient } from "./client.js";
import {
  FetchMasterAccountInput,
  FetchPositionsInput,
  FetchTaxlotsInput,
} from "./schemas.js";

export function buildTools(
  client: SchwabClient,
): Readonly<Record<string, ToolDefinition>> {
  return Object.freeze({
    "schwab.fetch_positions": {
      name: "schwab.fetch_positions",
      description:
        "Fetch positions for a Schwab account — returns raw vendor JSON — use M7 translator to canonicalize. READ-ONLY (trade submission is Phase 3 per Appendix E row 24).",
      input: FetchPositionsInput,
      handler: (args, ctx) =>
        client.fetchPositions(args as never, ctx.firmId),
    },
    "schwab.fetch_taxlots": {
      name: "schwab.fetch_taxlots",
      description:
        "Fetch tax lots for a Schwab account — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchTaxlotsInput,
      handler: (args, ctx) =>
        client.fetchTaxlots(args as never, ctx.firmId),
    },
    "schwab.fetch_master_account": {
      name: "schwab.fetch_master_account",
      description:
        "Fetch a Schwab master-account with optional linked accounts — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchMasterAccountInput,
      handler: (args, ctx) =>
        client.fetchMasterAccount(args as never, ctx.firmId),
    },
  });
}

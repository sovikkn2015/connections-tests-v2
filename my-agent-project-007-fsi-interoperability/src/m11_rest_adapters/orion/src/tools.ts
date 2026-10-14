/** Orion frozen tool registry. Spec AC2.2. */

import type { ToolDefinition } from "@project-007/mcp-sdk";

import type { OrionClient } from "./client.js";
import {
  FetchHoldingsInput,
  FetchHouseholdInput,
  FetchTaxlotsInput,
  FetchTransactionsInput,
} from "./schemas.js";

export function buildTools(
  client: OrionClient,
): Readonly<Record<string, ToolDefinition>> {
  return Object.freeze({
    "orion.fetch_holdings": {
      name: "orion.fetch_holdings",
      description:
        "Fetch positions for an Orion account — returns raw vendor JSON — use M7 translator to canonicalize. Paths PENDING-VERIFICATION.",
      input: FetchHoldingsInput,
      handler: (args, ctx) => client.fetchHoldings(args as never, ctx.firmId),
    },
    "orion.fetch_transactions": {
      name: "orion.fetch_transactions",
      description:
        "Fetch transactions for an Orion account within a ≤ 90-day window — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchTransactionsInput,
      handler: (args, ctx) =>
        client.fetchTransactions(args as never, ctx.firmId),
    },
    "orion.fetch_household": {
      name: "orion.fetch_household",
      description:
        "Fetch an Orion household — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchHouseholdInput,
      handler: (args, ctx) =>
        client.fetchHousehold(args as never, ctx.firmId),
    },
    "orion.fetch_taxlots": {
      name: "orion.fetch_taxlots",
      description:
        "Fetch tax lots for an Orion account — returns raw vendor JSON — use M7 translator to canonicalize.",
      input: FetchTaxlotsInput,
      handler: (args, ctx) =>
        client.fetchTaxlots(args as never, ctx.firmId),
    },
  });
}

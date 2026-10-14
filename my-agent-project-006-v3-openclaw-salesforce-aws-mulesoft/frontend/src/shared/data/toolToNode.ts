/**
 * Maps inbound `tool_name` strings to topology node ids used by the live map.
 */

import type { Persona } from '../types/persona';

/** Canonical skill-name → topology node id. Skill nodes live at layer 3. */
const SKILL_TOOL_MAP: Record<string, string> = {
  // research skills
  rag_retrieve: 'skill:rag_retrieve',
  financial_statement_analysis: 'skill:financial_statement_analysis',
  research_awareness: 'skill:research_awareness',
  publish_brief: 'skill:publish_brief',
  // advisor skills
  portfolio_analytics: 'skill:portfolio_analytics',
  scenario_modeling: 'skill:scenario_modeling',
  suitability_check: 'skill:suitability_check',
  client_summary: 'skill:client_summary',
  // action / trust-path skills
  compliance_screening: 'skill:compliance_screening',
  hitl: 'skill:hitl',
  dual_auth: 'skill:dual_auth',
  mulesoft_api: 'skill:mulesoft_api',
  audit_logging: 'skill:audit_logging',
};

/** MCP tool-name → MCP node id (layer 4). */
const MCP_TOOL_MAP: Record<string, string> = {
  // salesforce-crm
  run_soql_query: 'salesforce-crm',
  soql_query: 'salesforce-crm',
  get_household: 'salesforce-crm',
  get_positions: 'salesforce-crm',
  get_client_contact: 'salesforce-crm',
  // market-data
  get_quote: 'market-data',
  get_price: 'market-data',
  get_technicals: 'market-data',
  // sec-edgar
  get_10k: 'sec-edgar',
  get_10q: 'sec-edgar',
  get_8k: 'sec-edgar',
  get_filing: 'sec-edgar',
  // news-search
  search_financial_news: 'news-search',
  search_news: 'news-search',
  tavily_search: 'news-search',
  // mulesoft-actions
  submit_order: 'mulesoft-actions',
  cancel_order: 'mulesoft-actions',
  modify_order: 'mulesoft-actions',
  initiate_wire: 'mulesoft-actions',
};

/** Substring hints for unknown tool names — tried in order, first match wins. */
const HEURISTIC_HINTS: ReadonlyArray<readonly [string, string]> = [
  ['soql', 'salesforce-crm'],
  ['salesforce', 'salesforce-crm'],
  ['quote', 'market-data'],
  ['finnhub', 'market-data'],
  ['edgar', 'sec-edgar'],
  ['10k', 'sec-edgar'],
  ['10q', 'sec-edgar'],
  ['filing', 'sec-edgar'],
  ['tavily', 'news-search'],
  ['news', 'news-search'],
  ['mulesoft', 'mulesoft-actions'],
  ['wire', 'mulesoft-actions'],
  ['order', 'mulesoft-actions'],
];

/** Persona → preferred skill/MCP fallbacks when a tool name is ambiguous. */
const PERSONA_FALLBACKS: Record<Persona, readonly string[]> = {
  fsi_research: ['salesforce-crm', 'sec-edgar'],
  fsi_advisor: ['salesforce-crm', 'mulesoft-actions'],
  fsi_client_liaison: ['salesforce-crm'],
};

function warnOnce(toolName: string): void {
  if (typeof process !== 'undefined' && process.env?.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.warn(`[toolToNode] unknown tool name: ${toolName}`);
  }
}

/**
 * Resolve a tool name to a topology node id.
 *
 * Resolution order:
 *   1. exact skill-name match (case-insensitive)
 *   2. exact MCP-name match (case-insensitive)
 *   3. substring heuristic on well-known vendor keywords
 *   4. persona fallback (if provided)
 *   5. null + dev-mode console.warn
 */
export function resolveNodeId(toolName: string, agentPersona?: Persona): string | null {
  if (!toolName) return null;
  const key = toolName.toLowerCase();

  const skill = SKILL_TOOL_MAP[key];
  if (skill) return skill;

  const mcp = MCP_TOOL_MAP[key];
  if (mcp) return mcp;

  for (const [needle, node] of HEURISTIC_HINTS) {
    if (key.includes(needle)) return node;
  }

  if (agentPersona) {
    const fallback = PERSONA_FALLBACKS[agentPersona][0];
    if (fallback) return fallback;
  }

  warnOnce(toolName);
  return null;
}

/** Exposed for tests + the store — gives the raw table keys. */
export const KNOWN_SKILL_TOOLS: ReadonlySet<string> = new Set(Object.keys(SKILL_TOOL_MAP));
export const KNOWN_MCP_TOOLS: ReadonlySet<string> = new Set(Object.keys(MCP_TOOL_MAP));

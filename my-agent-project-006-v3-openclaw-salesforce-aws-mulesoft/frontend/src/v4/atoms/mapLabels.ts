/**
 * Business-friendly labels for the Architecture Map.
 *
 * Why this exists: the topology.json IDs are engineering codenames
 * (`filings_specialist`, `research_orchestrator`, `mcp:sec-edgar`,
 * `skill:rag_retrieve`). A demo reviewer, a compliance officer, or an
 * exec can't parse those. Three zoom levels let each audience see the
 * register they need without hiding the truth.
 *
 * Levels:
 *   - simple:    what a business viewer sees on first open. ~9 nodes.
 *                Plain English; the four specialists an analyst talks
 *                about ("SEC filings", "Market data", "News sentiment",
 *                "Financials"), one "Compliance check", one "Research
 *                Analyst" agent and the coordinator. That's the whole
 *                story.
 *   - detailed:  the same plain-English names but adds the other two
 *                orchestrators (advisor, client) + their specialists +
 *                the data sources as labelled tools beneath each
 *                specialist. Still readable without codenames.
 *   - developer: the full topology.json graph with engineering IDs.
 *                For audit, debugging, and the people who ship it.
 *
 * Derivation: every node in topology.json is included in exactly one
 * of the three levels; business + detailed labels are derived from the
 * topology `detail` field where sensible, otherwise hand-mapped. This
 * file is the ONLY place business copy lives — change a label once,
 * it flows everywhere.
 */

import type { Persona } from '../../shared/types/persona';

export type MapLevel = 'simple' | 'detailed' | 'developer';

export interface NodeLabels {
  simple: string; // plain-English label for business view
  detailed: string; // plain-English but more specific
  kindSimple: 'agent' | 'data' | 'gate' | 'root'; // simplified kind for colour
}

/**
 * Business + detailed labels keyed by topology node id. IDs not present
 * here are auto-hidden in simple level, auto-labelled in detailed by
 * stripping underscores, and always rendered with their raw id in
 * developer mode.
 */
export const NODE_LABELS: Record<string, NodeLabels> = {
  // --- Coordinator ---
  coordinator: {
    simple: 'FSI Workforce 360',
    detailed: 'Coordinator',
    kindSimple: 'root',
  },

  // --- Orchestrators (the "agents" a business viewer meets) ---
  research_orchestrator: {
    simple: 'Research Analyst',
    detailed: 'Research Agent',
    kindSimple: 'agent',
  },
  advisor_orchestrator: {
    simple: 'Wealth Advisor',
    detailed: 'Advisor Agent',
    kindSimple: 'agent',
  },
  liaison_orchestrator: {
    simple: 'Client Liaison',
    detailed: 'Liaison Agent',
    kindSimple: 'agent',
  },

  // --- Research specialists (plain English, one line) ---
  market_specialist: {
    simple: 'Market Data',
    detailed: 'Market Data · prices, volume, technicals',
    kindSimple: 'agent',
  },
  filings_specialist: {
    simple: 'SEC Filings',
    detailed: 'SEC Filings · 10-K / 10-Q / 8-K',
    kindSimple: 'agent',
  },
  sentiment_specialist: {
    simple: 'News Sentiment',
    detailed: 'News Sentiment · 30-day headlines',
    kindSimple: 'agent',
  },
  statement_specialist: {
    simple: 'Financials',
    detailed: 'Financials · growth, margins, ratios',
    kindSimple: 'agent',
  },
  compliance_specialist: {
    simple: 'Compliance Check',
    detailed: 'Compliance Check · restricted list + MNPI',
    kindSimple: 'gate',
  },

  // --- Advisor specialists ---
  action_specialist: {
    simple: 'Order Drafter',
    detailed: 'Order Drafter · write-path planner',
    kindSimple: 'agent',
  },
  suitability_specialist: {
    simple: 'Suitability',
    detailed: 'Suitability · IPS rules check',
    kindSimple: 'gate',
  },
  portfolio_specialist: {
    simple: 'Portfolio Analytics',
    detailed: 'Portfolio Analytics · concentration, drawdown',
    kindSimple: 'agent',
  },
  client_context_specialist: {
    simple: 'Client Context',
    detailed: 'Client Context · 30-second RM prep',
    kindSimple: 'agent',
  },

  // --- Liaison specialists ---
  faq_specialist: {
    simple: 'FAQ',
    detailed: 'FAQ · client-safe answers',
    kindSimple: 'agent',
  },
  context_specialist: {
    simple: 'Client Context',
    detailed: 'Client Context · MNPI-safe read',
    kindSimple: 'agent',
  },

  // --- Trust layer ---
  mnpi_filter: {
    simple: 'MNPI Filter',
    detailed: 'MNPI Filter · server-side redaction',
    kindSimple: 'gate',
  },
  gate_enforcer: {
    simple: '7-Gate Policy',
    detailed: '7-Gate Policy · write-path gate sequencer',
    kindSimple: 'gate',
  },
  idp_session: {
    simple: 'Sign-in',
    detailed: 'IdP Session · auth + session HMAC',
    kindSimple: 'gate',
  },

  // --- MCPs (data sources) ---
  'market-data': {
    simple: 'Finnhub',
    detailed: 'Finnhub Quotes',
    kindSimple: 'data',
  },
  'sec-edgar': {
    simple: 'SEC EDGAR',
    detailed: 'SEC EDGAR filings',
    kindSimple: 'data',
  },
  'news-search': {
    simple: 'Tavily News',
    detailed: 'Tavily News search',
    kindSimple: 'data',
  },
  'salesforce-crm': {
    simple: 'Salesforce',
    detailed: 'Salesforce CRM',
    kindSimple: 'data',
  },
  'mulesoft-actions': {
    simple: 'MuleSoft',
    detailed: 'MuleSoft Actions gateway',
    kindSimple: 'data',
  },

  // --- Gates (write-path) — business names ---
  'gate:guardrails': {
    simple: 'Guardrails',
    detailed: '① Guardrails',
    kindSimple: 'gate',
  },
  'gate:mnpi_filter': {
    simple: 'MNPI Filter',
    detailed: '② MNPI Filter',
    kindSimple: 'gate',
  },
  'gate:compliance': {
    simple: 'Compliance',
    detailed: '③ Compliance',
    kindSimple: 'gate',
  },
  'gate:hitl': {
    simple: 'RM Approval',
    detailed: '④ HITL · RM approves',
    kindSimple: 'gate',
  },
  'gate:dual_auth': {
    simple: 'Dual Auth',
    detailed: '⑤ Dual Auth',
    kindSimple: 'gate',
  },
  'gate:mulesoft': {
    simple: 'Broker Submit',
    detailed: '⑥ MuleSoft · OMS submit',
    kindSimple: 'gate',
  },
  'gate:audit': {
    simple: 'Audit',
    detailed: '⑦ Audit · Langfuse + CRM',
    kindSimple: 'gate',
  },
};

/**
 * Which node ids appear at each zoom level, per active persona.
 * Developer mode shows all — no filtering.
 */
export function idsAtLevel(level: MapLevel, persona: Persona): Set<string> | null {
  if (level === 'developer') return null; // null = "show everything"

  const common = ['coordinator', 'mnpi_filter'];

  if (level === 'simple') {
    // Just the active persona's orchestrator + its named specialists +
    // the compliance gate. Every persona gets the same minimal rhythm.
    if (persona === 'fsi_research') {
      return new Set([
        ...common,
        'research_orchestrator',
        'market_specialist',
        'filings_specialist',
        'sentiment_specialist',
        'statement_specialist',
        'compliance_specialist',
      ]);
    }
    if (persona === 'fsi_advisor') {
      return new Set([
        ...common,
        'advisor_orchestrator',
        'action_specialist',
        'suitability_specialist',
        'portfolio_specialist',
        'client_context_specialist',
        'gate_enforcer',
      ]);
    }
    return new Set([
      ...common,
      'liaison_orchestrator',
      'faq_specialist',
      'context_specialist',
    ]);
  }

  // Detailed: the three orchestrators stay visible (shared trust spine),
  // active persona's specialists AND their MCPs, plus the compliance /
  // gate layer.
  const detailed = new Set([
    'coordinator',
    'research_orchestrator',
    'advisor_orchestrator',
    'liaison_orchestrator',
    'mnpi_filter',
    'gate_enforcer',
  ]);
  if (persona === 'fsi_research') {
    [
      'market_specialist',
      'filings_specialist',
      'sentiment_specialist',
      'statement_specialist',
      'compliance_specialist',
      'market-data',
      'sec-edgar',
      'news-search',
    ].forEach((id) => detailed.add(id));
  } else if (persona === 'fsi_advisor') {
    [
      'action_specialist',
      'suitability_specialist',
      'portfolio_specialist',
      'client_context_specialist',
      'salesforce-crm',
      'mulesoft-actions',
      // gate chain when advisor write is in flight — added elsewhere based
      // on gateChainVisible, but we include them in "detailed" because the
      // chain IS the point of the advisor view
      'gate:guardrails',
      'gate:mnpi_filter',
      'gate:compliance',
      'gate:hitl',
      'gate:dual_auth',
      'gate:mulesoft',
      'gate:audit',
    ].forEach((id) => detailed.add(id));
  } else {
    [
      'faq_specialist',
      'context_specialist',
      'salesforce-crm',
      'news-search',
    ].forEach((id) => detailed.add(id));
  }
  return detailed;
}

/**
 * Pick the right label for a node at a zoom level.
 */
export function labelFor(id: string, level: MapLevel): string {
  const entry = NODE_LABELS[id];
  if (level === 'developer') return id.replace(/^skill:/, '').replace(/^gate:/, '');
  if (!entry) {
    // Fallback when a node isn't in the lookup — humanise the id
    return id.replace(/^skill:/, '').replace(/^gate:/, '').replace(/_/g, ' ');
  }
  return level === 'simple' ? entry.simple : entry.detailed;
}

/**
 * Simplified kind for colour — business view groups kinds into
 * agent / data / gate / root instead of the 6 internal kinds.
 */
export function kindSimpleFor(id: string, fallback: string): NodeLabels['kindSimple'] {
  const entry = NODE_LABELS[id];
  if (entry) return entry.kindSimple;
  if (fallback === 'coordinator') return 'root';
  if (fallback === 'mcp' || fallback === 'skill') return 'data';
  if (fallback === 'gate' || fallback === 'trust') return 'gate';
  return 'agent';
}

/**
 * Human-readable caption below the map explaining what the active
 * persona's workflow does. Rendered at every zoom level — the map
 * is the picture, the caption is the story.
 */
export function captionFor(persona: Persona): string {
  if (persona === 'fsi_research') {
    return 'The Research Analyst pulls in SEC filings, market quotes, news sentiment and financials in parallel — every read is screened for material non-public information before it reaches Sarah\u2019s brief.';
  }
  if (persona === 'fsi_advisor') {
    return 'The Wealth Advisor drafts an order plan. It must pass seven policy gates — including RM approval — before the broker ever sees it. Every outcome is audited.';
  }
  return 'The Client Liaison answers FAQs on Eleanor\u2019s phone. Any question that needs a recommendation hands off to her Wealth Advisor. The same trust spine that lights up for Sarah and Marcus lights up here.';
}

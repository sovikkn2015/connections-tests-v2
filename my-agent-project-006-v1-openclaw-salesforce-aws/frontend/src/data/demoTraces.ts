/**
 * Demo traces — pre-loaded examples showing end-to-end traceability.
 * These appear in the trace panel on first load so it's not empty.
 * Cleared when the user sends their first real query.
 *
 * Shows realistic multi-tool, multi-server query patterns:
 * 1. Simple CRM lookup (1 tool)
 * 2. Multi-source research (5 tools across 3 MCP servers)
 * 3. Full pipeline deep dive (8 tools across 4 MCP servers)
 */

import type { Message, ToolEvent } from '../types';

const BASE = Date.now() - 120_000; // 2 minutes ago

function ts(offsetMs: number): Date {
  return new Date(BASE + offsetMs);
}

export const DEMO_MESSAGES: Message[] = [
  // Query 1: Simple CRM lookup
  { id: 'demo-q1', role: 'user', text: 'Who covers NVDA on our team?', timestamp: ts(0) },
  {
    id: 'demo-a1', role: 'agent', timestamp: ts(1800),
    text: 'Sarah Kim (Goldman Sachs) covers NVDA with a Buy rating and $170 target price, last updated March 20, 2026. Source: salesforce-crm (SOQL), as of 2026-04-22T10:30:01Z.',
  },

  // Query 2: Multi-source research
  { id: 'demo-q2', role: 'user', text: "What's happening with NVIDIA ahead of earnings?", timestamp: ts(5000) },
  {
    id: 'demo-a2', role: 'agent', timestamp: ts(12000),
    text: 'NVIDIA (NVDA) is trading at $202.50 (+1.31%) ahead of its May 28 earnings report. The latest 10-K (filed 2026-02-25) shows $80B revenue, up 31% YoY driven by data center GPU demand. Analyst consensus is Buy with an average target of $161.67. Recent news is mixed — strong AI demand coverage offset by valuation concerns. Source: market-data (Finnhub), sec-edgar (SEC EDGAR API), salesforce-crm (Salesforce CRM), news-search (Tavily).',
  },

  // Query 3: Full pipeline deep dive
  { id: 'demo-q3', role: 'user', text: 'Deep dive on NVIDIA ahead of earnings', timestamp: ts(20000) },
  {
    id: 'demo-a3', role: 'agent', timestamp: ts(55000),
    text: 'Research brief generated for NVIDIA Corporation (NVDA). Rating: Buy, Target Price: $185. The 23-stage AutoResearchClaw pipeline completed with 3 HITL gates approved. DCF fair value: $158.90 (17.4% upside). Monte Carlo median: $152.30 (P5: $88.50, P95: $225.80). Key catalyst: Blackwell GPU demand exceeding supply. Primary risk: valuation premium at 65x trailing PE. Full brief saved to IR_Research_Note__c. Source: market-data, sec-edgar, news-search, salesforce-crm.',
  },
];

export const DEMO_TOOL_EVENTS: ToolEvent[] = [
  // ── Query 1: CRM lookup (1 tool) ──
  {
    id: 'demo-t1-start', name: 'run_soql_query', phase: 'start', timestamp: ts(200),
    input: { query: "SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c FROM IR_Coverage__c WHERE Company__r.Ticker__c='NVDA'" },
  },
  {
    id: 'demo-t1', name: 'run_soql_query', phase: 'result', timestamp: ts(540), duration: 340,
    result: { totalSize: 1, records: [{ Analyst__c: 'Sarah Kim', Rating__c: 'Buy', Target_Price__c: 170, Last_Updated__c: '2026-03-20', Firm__c: 'Goldman Sachs' }] },
  },

  // ── Query 2: Multi-source (5 tools, 3 servers) ──
  { id: 'demo-t2a-start', name: 'run_soql_query', phase: 'start', timestamp: ts(5200), input: { query: "SELECT Name, Ticker__c, Sector__c FROM IR_Company__c WHERE Ticker__c='NVDA'" } },
  { id: 'demo-t2a', name: 'run_soql_query', phase: 'result', timestamp: ts(5520), duration: 320, result: { totalSize: 1, records: [{ Name: 'NVIDIA Corporation', Ticker__c: 'NVDA', Sector__c: 'Technology' }] } },

  { id: 'demo-t2b-start', name: 'get_quote', phase: 'start', timestamp: ts(5300), input: { symbol: 'NVDA' } },
  { id: 'demo-t2b', name: 'get_quote', phase: 'result', timestamp: ts(5980), duration: 680, result: { symbol: 'NVDA', price: 202.5, change: 2.62, changePercent: 1.31, dataSource: 'Finnhub' } },

  { id: 'demo-t2c-start', name: 'get_10k', phase: 'start', timestamp: ts(5400), input: { ticker: 'NVDA', count: 1 } },
  { id: 'demo-t2c', name: 'get_10k', phase: 'result', timestamp: ts(8600), duration: 3200, result: { ticker: 'NVDA', form: '10-K', filings: [{ filingDate: '2026-02-25', accessionNumber: '0001045810-26-000021' }] } },

  { id: 'demo-t2d-start', name: 'get_analyst_consensus', phase: 'start', timestamp: ts(5500), input: { symbol: 'NVDA' } },
  { id: 'demo-t2d', name: 'get_analyst_consensus', phase: 'result', timestamp: ts(6400), duration: 900, result: { buyCount: 3, holdCount: 0, sellCount: 0, avgTargetPrice: 161.67 } },

  { id: 'demo-t2e-start', name: 'search_financial_news', phase: 'start', timestamp: ts(5600), input: { query: 'NVDA stock earnings', max_results: 5 } },
  { id: 'demo-t2e', name: 'search_financial_news', phase: 'result', timestamp: ts(8400), duration: 2800, result: { articles: [{ title: 'NVIDIA Blackwell demand exceeds supply by 2x' }, { title: 'AI chip stocks rally ahead of earnings season' }, { title: 'Analysts debate NVDA valuation at 65x PE' }] } },

  // ── Query 3: Full pipeline (8 tools, 4 servers) ──
  { id: 'demo-t3a-start', name: 'run_soql_query', phase: 'start', timestamp: ts(20200), input: { query: "SELECT Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c, Description__c FROM IR_Company__c WHERE Ticker__c='NVDA'" } },
  { id: 'demo-t3a', name: 'run_soql_query', phase: 'result', timestamp: ts(20550), duration: 350, result: { totalSize: 1, records: [{ Name: 'NVIDIA Corporation', Ticker__c: 'NVDA', Sector__c: 'Technology' }] } },

  { id: 'demo-t3b-start', name: 'run_soql_query', phase: 'start', timestamp: ts(20600), input: { query: "SELECT Analyst__c, Rating__c, Target_Price__c FROM IR_Coverage__c WHERE Company__r.Ticker__c='NVDA'" } },
  { id: 'demo-t3b', name: 'run_soql_query', phase: 'result', timestamp: ts(20920), duration: 320, result: { totalSize: 3, records: [{ Analyst__c: 'Sarah Kim', Rating__c: 'Buy', Target_Price__c: 170 }] } },

  { id: 'demo-t3c-start', name: 'get_quote', phase: 'start', timestamp: ts(21000), input: { symbol: 'NVDA' } },
  { id: 'demo-t3c', name: 'get_quote', phase: 'result', timestamp: ts(21650), duration: 650, result: { symbol: 'NVDA', price: 202.5, change: 2.62, changePercent: 1.31 } },

  { id: 'demo-t3d-start', name: 'get_price_history', phase: 'start', timestamp: ts(21100), input: { symbol: 'NVDA', period: '1y' } },
  { id: 'demo-t3d', name: 'get_price_history', phase: 'result', timestamp: ts(22200), duration: 1100, result: { symbol: 'NVDA', points: 252 } },

  { id: 'demo-t3e-start', name: 'get_10k', phase: 'start', timestamp: ts(21200), input: { ticker: 'NVDA', count: 1 } },
  { id: 'demo-t3e', name: 'get_10k', phase: 'result', timestamp: ts(24400), duration: 3200, result: { ticker: 'NVDA', form: '10-K', filings: [{ filingDate: '2026-02-25' }] } },

  { id: 'demo-t3f-start', name: 'get_8k', phase: 'start', timestamp: ts(21300), input: { ticker: 'NVDA', count: 5 } },
  { id: 'demo-t3f', name: 'get_8k', phase: 'result', timestamp: ts(23800), duration: 2500, result: { ticker: 'NVDA', form: '8-K', filings: [{ filingDate: '2026-03-05' }, { filingDate: '2026-01-15' }] } },

  { id: 'demo-t3g-start', name: 'search_financial_news', phase: 'start', timestamp: ts(21400), input: { query: 'NVDA stock', max_results: 20 } },
  { id: 'demo-t3g', name: 'search_financial_news', phase: 'result', timestamp: ts(24200), duration: 2800, result: { articles: [{ title: 'NVIDIA Blackwell demand exceeds supply' }, { title: 'AI infrastructure buildout is a multi-year cycle' }] } },

  { id: 'demo-t3h-start', name: 'get_analyst_consensus', phase: 'start', timestamp: ts(21500), input: { symbol: 'NVDA' } },
  { id: 'demo-t3h', name: 'get_analyst_consensus', phase: 'result', timestamp: ts(22400), duration: 900, result: { buyCount: 3, holdCount: 0, sellCount: 0, avgTargetPrice: 161.67, highTargetPrice: 170, lowTargetPrice: 155 } },
];

/**
 * Zustand store — single source of truth for agent state.
 * Extended from 005 V2 with pipeline, HITL, tool events, and brief data.
 * Connects to OpenClaw via WebSocket (not Salesforce Agent API).
 */

import { create } from 'zustand';
import type {
  Message,
  CompanyData,
  CoverageData,
  ChartDataPoint,
  FilingData,
  ResearchTab,
  UserInfo,
  ConsensusSummary,
  ValuationData,
  SentimentData,
  ChartMetric,
  FilingFilter,
  PipelineStage,
  HitlGate,
  ToolEvent,
  BriefData,
} from '../types';
import * as openclawApi from '../services/openclawApi';
import { setConnectionChangeCallback, isRateLimited } from '../services/openclawApi';
import {
  COMPANY_PROFILES,
  ANALYST_COVERAGE,
  CONSENSUS_SUMMARIES,
  CHART_DATA,
  SAMPLE_FILINGS,
  VALUATION_SNAPSHOTS,
  SENTIMENT_SNAPSHOTS,
  isSupported,
} from '../data/seedData';
import { DEMO_MESSAGES, DEMO_TOOL_EVENTS } from '../data/demoTraces';

/**
 * Build a blank CompanyData shell for tickers not in seed data.
 * Populated progressively as tool results arrive.
 */
function blankCompany(ticker: string): CompanyData {
  return {
    name: ticker, ticker, sector: '', exchange: '', marketCap: '',
    peRatio: '', earningsDate: '', weekHigh52: '', weekLow52: '',
    description: '', industry: '', price: 0, change: 0, changePct: 0,
    beta: '', dividendYield: '', forwardPE: '', profitMargin: '',
    epsttm: '', revenuePerShare: '', movingAvg50: '', movingAvg200: '',
  };
}

interface AgentState {
  /* ── Auth (SF identity only) ── */
  sfToken: string | null;
  instanceUrl: string | null;
  userInfo: UserInfo | null;
  logIn: (() => void) | null;
  logOut: (() => void) | null;
  setAuth: (token: string, instanceUrl: string, user: UserInfo) => void;
  setAuthCallbacks: (logIn: () => void, logOut: () => void) => void;
  clearAuth: () => void;

  /* ── OpenClaw Connection ── */
  connected: boolean;
  sessionKey: string;
  error: string | null;
  connectToOpenClaw: () => Promise<void>;
  disconnectFromOpenClaw: () => void;

  /* ── Chat ── */
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (text: string) => Promise<void>;
  clearMessages: () => void;

  /* ── Research Data ── */
  activeTab: ResearchTab;
  setActiveTab: (tab: ResearchTab) => void;
  activeTicker: string | null;
  companyData: CompanyData | null;
  coverageData: CoverageData[];
  chartData: ChartDataPoint[];
  filings: FilingData[];
  consensusSummary: ConsensusSummary | null;
  valuationData: ValuationData | null;
  sentimentData: SentimentData | null;
  chartMetric: ChartMetric;
  filingFilter: FilingFilter;
  setChartMetric: (metric: ChartMetric) => void;
  setFilingFilter: (filter: FilingFilter) => void;
  loadTickerData: (ticker: string) => void;

  /* ── Pipeline (006-specific) ── */
  pipelineStages: PipelineStage[];
  currentStageId: number | null;
  hitlGate: HitlGate | null;
  approveHitlGate: () => void;
  rejectHitlGate: () => void;

  /* ── Tool Events (006-specific) ── */
  toolEvents: ToolEvent[];

  /* ── Brief (006-specific) ── */
  briefData: BriefData | null;

  /* ── Trace Panel ── */
  traceExpanded: boolean;
  toggleTrace: () => void;
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** Default 23-stage AutoResearchClaw pipeline */
// Pipeline stage definitions — HITL gates at stages 7, 13, 21
// Must match config.arc.yaml hitl.stage_policies and pipeline.py HITL_STAGES
function defaultPipelineStages(): PipelineStage[] {
  const stages: { name: string; phase: string; isHitlGate: boolean }[] = [
    { name: 'Intake & Parse', phase: 'A: Intake', isHitlGate: false },
    { name: 'CRM Context Fetch', phase: 'A: Intake', isHitlGate: false },
    { name: 'Market Data Pull', phase: 'B: Data Collection', isHitlGate: false },
    { name: 'News & Sentiment Scan', phase: 'B: Data Collection', isHitlGate: false },
    { name: 'SEC Filing Retrieval', phase: 'B: Data Collection', isHitlGate: false },
    { name: 'Transcript Analysis', phase: 'B: Data Collection', isHitlGate: false },
    { name: 'Data Quality Gate', phase: 'C: Validation', isHitlGate: true },
    { name: 'Financial Modeling', phase: 'D: Analysis', isHitlGate: false },
    { name: 'DCF Valuation', phase: 'D: Analysis', isHitlGate: false },
    { name: 'Comps Analysis', phase: 'D: Analysis', isHitlGate: false },
    { name: 'Monte Carlo Simulation', phase: 'D: Analysis', isHitlGate: false },
    { name: 'Sentiment Synthesis', phase: 'D: Analysis', isHitlGate: false },
    { name: 'Analysis Review Gate', phase: 'E: Review', isHitlGate: true },
    { name: 'Thesis Generation', phase: 'F: Synthesis', isHitlGate: false },
    { name: 'Catalyst Identification', phase: 'F: Synthesis', isHitlGate: false },
    { name: 'Risk Assessment', phase: 'F: Synthesis', isHitlGate: false },
    { name: 'Rating Determination', phase: 'F: Synthesis', isHitlGate: false },
    { name: 'Target Price Calc', phase: 'F: Synthesis', isHitlGate: false },
    { name: 'Brief Assembly', phase: 'G: Output', isHitlGate: false },
    { name: 'Compliance Check', phase: 'G: Output', isHitlGate: false },
    { name: 'Final Approval Gate', phase: 'H: Delivery', isHitlGate: true },
    { name: 'CRM Write-back', phase: 'H: Delivery', isHitlGate: false },
    { name: 'Delivery & Notify', phase: 'H: Delivery', isHitlGate: false },
  ];
  return stages.map((s, i) => ({
    id: i + 1,
    name: s.name,
    phase: s.phase,
    status: 'pending' as const,
    isHitlGate: s.isHitlGate,
  }));
}


/* ── Helper: safely extract JSON from MCP tool result ── */
function parseMcpResult(result: unknown): Record<string, unknown> | null {
  try {
    if (typeof result === 'string') return JSON.parse(result);
    if (result && typeof result === 'object') {
      const r = result as Record<string, unknown>;
      // MCP content wrapper: { content: [{ text: "..." }] } or { text: "..." }
      if (typeof r.text === 'string') return JSON.parse(r.text);
      if (Array.isArray(r.content)) {
        const first = (r.content as Record<string, unknown>[])[0];
        if (first && typeof first.text === 'string') return JSON.parse(first.text);
      }
      // Already a plain object
      return r;
    }
  } catch { /* not valid JSON */ }
  return null;
}

/* ── Helper: process MCP tool results into research panel state ── */
function processToolResult(
  name: string,
  result: unknown,
  get: () => AgentState,
  set: (partial: Partial<AgentState> | ((s: AgentState) => Partial<AgentState>)) => void,
) {
  const data = parseMcpResult(result);
  if (!data) return;

  switch (name) {
    /* ── Market Data MCP ── */
    case 'get_quote': {
      const existing = get().companyData;
      if (!existing) break;
      const price = parseFloat(String(data.price ?? ''));
      const change = parseFloat(String(data.change ?? ''));
      const pctRaw = String(data.changePercent ?? '').replace('%', '');
      const changePct = parseFloat(pctRaw);
      if (isNaN(price)) break;
      set({
        companyData: {
          ...existing,
          price,
          change: isNaN(change) ? existing.change : change,
          changePct: isNaN(changePct) ? existing.changePct : changePct,
        },
      });
      // Also keep consensusSummary.currentPrice in sync
      const cs = get().consensusSummary;
      if (cs) {
        set({ consensusSummary: { ...cs, currentPrice: price } });
      }
      break;
    }

    case 'get_price_history': {
      // Expects an array of OHLCV records (or a wrapper with a `data`/`history` key)
      const rows = (Array.isArray(data) ? data : (data.data ?? data.history ?? data.prices)) as
        | { date?: string; close?: number; open?: number; high?: number; low?: number; volume?: number }[]
        | undefined;
      if (!Array.isArray(rows) || rows.length === 0) break;
      const points: ChartDataPoint[] = rows.map((r) => ({
        date: r.date ?? '',
        revenue: 0,
        eps: 0,
        price: typeof r.close === 'number' ? r.close : undefined,
      }));
      set({ chartData: points });
      break;
    }

    case 'get_analyst_consensus': {
      const buy = parseInt(String(data.buyCount ?? data.buy ?? 0), 10);
      const hold = parseInt(String(data.holdCount ?? data.hold ?? 0), 10);
      const sell = parseInt(String(data.sellCount ?? data.sell ?? 0), 10);
      const avg = parseFloat(String(data.avgTargetPrice ?? data.averageTarget ?? data.targetPrice ?? 0));
      const high = parseFloat(String(data.highTargetPrice ?? data.highTarget ?? avg));
      const low = parseFloat(String(data.lowTargetPrice ?? data.lowTarget ?? avg));
      const cur = parseFloat(String(data.currentPrice ?? 0));
      if (buy + hold + sell === 0 && avg === 0) break;
      const existing = get().consensusSummary;
      set({
        consensusSummary: {
          buyCount: buy || existing?.buyCount || 0,
          holdCount: hold || existing?.holdCount || 0,
          sellCount: sell || existing?.sellCount || 0,
          avgTargetPrice: avg || existing?.avgTargetPrice || 0,
          highTargetPrice: high || existing?.highTargetPrice || 0,
          lowTargetPrice: low || existing?.lowTargetPrice || 0,
          currentPrice: cur || existing?.currentPrice || get().companyData?.price || 0,
        },
      });
      break;
    }

    /* ── SEC EDGAR MCP ── */
    case 'get_10k':
    case 'get_10q':
    case 'get_8k': {
      const filings = (data.filings ?? data.results ?? data) as
        | { form?: string; filingDate?: string; accessionNumber?: string; documentUrl?: string; description?: string }[]
        | undefined;
      if (!Array.isArray(filings) || filings.length === 0) break;
      const formLabel = name.replace('get_', '').toUpperCase();
      const newFilings: FilingData[] = filings.map((f) => ({
        type: f.form ?? formLabel,
        date: f.filingDate ?? '',
        description: f.description ?? `${f.form ?? formLabel} filing`,
        url: f.documentUrl ?? '',
      }));
      // Merge: deduplicate by type+date to avoid duplicating seed data
      set((s) => {
        const existingKeys = new Set(s.filings.map((f) => `${f.type}|${f.date}`));
        const unique = newFilings.filter((f) => !existingKeys.has(`${f.type}|${f.date}`));
        return unique.length > 0 ? { filings: [...s.filings, ...unique] } : {};
      });
      break;
    }

    case 'get_insider_transactions': {
      const txns = (data.filings ?? data.transactions ?? data.results ?? data) as
        | { form?: string; filingDate?: string; transactionDate?: string; documentUrl?: string; ownerName?: string; transactionType?: string }[]
        | undefined;
      if (!Array.isArray(txns) || txns.length === 0) break;
      const newFilings: FilingData[] = txns.map((t) => ({
        type: t.form ?? 'Form 4',
        date: t.filingDate ?? t.transactionDate ?? '',
        description: [t.ownerName, t.transactionType].filter(Boolean).join(' — ') || 'Insider transaction',
        url: t.documentUrl ?? '',
      }));
      set((s) => {
        const existingKeys = new Set(s.filings.map((f) => `${f.type}|${f.date}|${f.description}`));
        const unique = newFilings.filter((f) => !existingKeys.has(`${f.type}|${f.date}|${f.description}`));
        return unique.length > 0 ? { filings: [...s.filings, ...unique] } : {};
      });
      break;
    }

    /* ── News MCP ── */
    case 'search_financial_news':
    case 'get_headlines': {
      // Extract sentiment signal from news articles when possible
      const articles = (data.articles ?? data.results ?? data.news ?? data) as
        | { title?: string; sentiment?: string; summary?: string }[]
        | undefined;
      if (!Array.isArray(articles) || articles.length === 0) break;
      const existing = get().sentimentData;
      // Build a lightweight news summary from article titles
      const headlines = articles
        .slice(0, 5)
        .map((a) => a.title)
        .filter(Boolean)
        .join('; ');
      set({
        sentimentData: {
          overallSentiment: existing?.overallSentiment ?? 'Neutral',
          confidence: existing?.confidence ?? 'Medium',
          sentimentScore: existing?.sentimentScore ?? 0.5,
          keyDrivers: existing?.keyDrivers ?? [],
          transcriptSentiment: existing?.transcriptSentiment ?? '',
          newsSentiment: headlines || existing?.newsSentiment || '',
        },
      });
      break;
    }

    /* ── Salesforce CRM MCP (run_soql_query) ── */
    case 'run_soql_query': {
      const records = (data.records ?? data.result ?? data) as Record<string, unknown>[] | undefined;
      if (!Array.isArray(records) || records.length === 0) break;
      const first = records[0];

      // Detect which object was queried by checking field names
      if ('Ticker__c' in first && 'Sector__c' in first) {
        // IR_Company__c result — hydrate company card
        const existing = get().companyData ?? blankCompany(String(first.Ticker__c ?? ''));
        set({
          companyData: {
            ...existing,
            name: String(first.Name ?? existing.name),
            ticker: String(first.Ticker__c ?? existing.ticker),
            sector: String(first.Sector__c ?? existing.sector),
            exchange: String(first.Exchange__c ?? existing.exchange),
            marketCap: first.Market_Cap__c ? `$${(Number(first.Market_Cap__c) / 1e9).toFixed(1)}B` : existing.marketCap,
            description: String(first.Description__c ?? existing.description),
          },
        });
      } else if ('Analyst__c' in first && 'Rating__c' in first && 'Target_Price__c' in first) {
        // IR_Coverage__c result — hydrate coverage table
        const coverage: CoverageData[] = records.map((r) => ({
          analyst: String(r.Analyst__c ?? ''),
          firm: String(r.Firm__c ?? ''),
          rating: String(r.Rating__c ?? 'Hold') as CoverageData['rating'],
          targetPrice: r.Target_Price__c ? `$${Number(r.Target_Price__c).toFixed(0)}` : '',
          lastUpdated: String(r.Last_Updated__c ?? ''),
          lastAction: r.Last_Action__c as CoverageData['lastAction'],
        }));
        set({ coverageData: coverage });
      } else if ('Summary__c' in first && 'Full_Brief__c' in first) {
        // IR_Research_Note__c result — hydrate brief viewer
        set({
          briefData: {
            ticker: String(first.Ticker__c ?? get().activeTicker ?? ''),
            company: String(first.Company__c ?? first.Name ?? ''),
            analyst: String(first.Analyst__c ?? ''),
            rating: String(first.Rating__c ?? ''),
            targetPrice: parseFloat(String(first.Target_Price__c ?? 0)),
            executiveSummary: String(first.Summary__c ?? ''),
            thesis: String(first.Thesis__c ?? first.Full_Brief__c ?? ''),
            catalysts: String(first.Catalysts__c ?? ''),
            risks: String(first.Risks__c ?? ''),
            valuation: String(first.Valuation__c ?? ''),
            generatedDate: String(first.Generated_Date__c ?? ''),
            pipelineRunId: String(first.Pipeline_Run_Id__c ?? ''),
          },
        });
      }
      break;
    }

    default:
      console.debug(`[agentStore] unhandled tool result for "${name}"`, data);
  }
}

export const useAgentStore = create<AgentState>((set, get) => ({
  /* ── Auth ── */
  sfToken: null,
  instanceUrl: null,
  userInfo: null,
  logIn: null,
  logOut: null,
  setAuth: (token, instanceUrl, user) =>
    set({ sfToken: token, instanceUrl, userInfo: user }),
  setAuthCallbacks: (logIn, logOut) => set({ logIn, logOut }),
  clearAuth: () => {
    openclawApi.disconnect();
    set({ sfToken: null, instanceUrl: null, userInfo: null, connected: false });
  },

  /* ── OpenClaw Connection ── */
  connected: false,
  sessionKey: `session-${Date.now()}`,
  error: null,

  connectToOpenClaw: async () => {
    try {
      // Subscribe to connection state changes from the WebSocket client
      setConnectionChangeCallback((isConnected) => {
        set({ connected: isConnected });
      });
      await openclawApi.connect();
      set({ connected: true, error: null });
    } catch (e) {
      set({ error: (e as Error).message, connected: false });
    }
  },

  disconnectFromOpenClaw: () => {
    openclawApi.disconnect();
    set({ connected: false });
  },

  /* ── Chat ── */
  messages: [...DEMO_MESSAGES],
  isStreaming: false,

  sendMessage: async (text: string) => {
    const { sessionKey, connected: isConn } = get();

    // Check rate limit before sending (Finding #6)
    if (isRateLimited()) {
      set({ error: 'Rate limited — max 5 messages per 10 seconds. Please wait.' });
      return;
    }

    const userMsg: Message = {
      id: uid(),
      role: 'user',
      text,
      timestamp: new Date(),
    };
    const agentMsg: Message = {
      id: uid(),
      role: 'agent',
      text: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    set((s) => ({
      messages: [...s.messages, userMsg, agentMsg],
      isStreaming: true,
      error: null,
    }));

    // If not connected to OpenClaw, simulate a local response
    if (!isConn) {
      setTimeout(() => {
        set((s) => {
          const msgs = [...s.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'agent') {
            msgs[msgs.length - 1] = {
              ...last,
              text: `[OpenClaw not connected] I received your query about "${text}". Connect to OpenClaw Gateway to get live agent responses. Research panel data is loaded from seed data.`,
              isStreaming: false,
            };
          }
          return { messages: msgs, isStreaming: false };
        });
      }, 500);
      return;
    }

    try {
      await openclawApi.sendMessage(text, sessionKey, 'fsi-research', {
        onText: (chunk: string) => {
          set((s) => {
            const msgs = [...s.messages];
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'agent') {
              msgs[msgs.length - 1] = { ...last, text: last.text + chunk };
            }
            return { messages: msgs };
          });
        },
        onToolStart: (name: string, toolCallId: string, input: unknown) => {
          const evt: ToolEvent = {
            id: toolCallId,
            name,
            phase: 'start',
            input,
            timestamp: new Date(),
          };
          set((s) => {
            const events = [...s.toolEvents, evt];
            // Cap at 500 events, drop oldest
            return { toolEvents: events.length > 500 ? events.slice(-500) : events };
          });
        },
        onToolResult: (toolName: string, toolCallId: string, result: unknown) => {
          set((s) => {
            const events = s.toolEvents.map((e) =>
              e.id === toolCallId
                ? { ...e, phase: 'result' as const, result, duration: Date.now() - e.timestamp.getTime() }
                : e,
            );
            return { toolEvents: events };
          });
          // Merge live MCP data into research panel state
          processToolResult(toolName, result, get, set);
        },
        onToolError: (_name: string, toolCallId: string, error: string) => {
          set((s) => {
            const events = s.toolEvents.map((e) =>
              e.id === toolCallId
                ? { ...e, phase: 'error' as const, error, duration: Date.now() - e.timestamp.getTime() }
                : e,
            );
            return { toolEvents: events };
          });
        },
        onLifecycle: (phase: 'start' | 'thinking' | 'end' | 'error') => {
          const { pipelineStages, currentStageId } = get();
          switch (phase) {
            case 'start': {
              // Reset all stages to pending and start from stage 1
              const reset: PipelineStage[] = pipelineStages.map((s) => ({
                ...s,
                status: 'pending' as const,
                startTime: undefined,
                endTime: undefined,
              }));
              reset[0] = { ...reset[0], status: 'running' as const, startTime: new Date() };
              set({ pipelineStages: reset, currentStageId: 1 });
              break;
            }
            case 'thinking': {
              // Complete current stage and advance to next
              if (!currentStageId) break;
              const nextId = currentStageId + 1;
              const updated = pipelineStages.map((s) => {
                if (s.id === currentStageId) {
                  return { ...s, status: 'completed' as const, endTime: new Date() };
                }
                if (s.id === nextId) {
                  return { ...s, status: 'running' as const, startTime: new Date() };
                }
                return s;
              });
              set({
                pipelineStages: updated,
                currentStageId: nextId <= pipelineStages.length ? nextId : currentStageId,
              });
              break;
            }
            case 'end': {
              // Mark current stage and all remaining as completed
              const completed = pipelineStages.map((s) =>
                s.status === 'running' || s.status === 'pending'
                  ? { ...s, status: 'completed' as const, endTime: s.endTime ?? new Date() }
                  : s,
              );
              set({ pipelineStages: completed, currentStageId: null });
              break;
            }
            case 'error': {
              // Mark current stage as failed
              const errored = pipelineStages.map((s) =>
                s.id === currentStageId
                  ? { ...s, status: 'failed' as const, endTime: new Date() }
                  : s,
              );
              set({ pipelineStages: errored, currentStageId: null });
              break;
            }
          }
        },
        onComplete: () => {
          set((s) => {
            const msgs = [...s.messages];
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'agent') {
              msgs[msgs.length - 1] = { ...last, isStreaming: false };
            }
            return { messages: msgs, isStreaming: false };
          });
        },
      });
    } catch (e) {
      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last && last.role === 'agent') {
          msgs[msgs.length - 1] = {
            ...last,
            text: last.text || `Error: ${(e as Error).message}`,
            isStreaming: false,
          };
        }
        return { messages: msgs, isStreaming: false, error: (e as Error).message };
      });
    }
  },

  clearMessages: () => set({ messages: [], toolEvents: [] }),

  /* ── Research Data ── */
  activeTab: 'company',
  setActiveTab: (tab) => set({ activeTab: tab }),
  activeTicker: null,
  companyData: null,
  coverageData: [],
  chartData: [],
  filings: [],
  consensusSummary: null,
  valuationData: null,
  sentimentData: null,
  chartMetric: 'revenue',
  filingFilter: 'All',
  setChartMetric: (metric) => set({ chartMetric: metric }),
  setFilingFilter: (filter) => set({ filingFilter: filter }),

  loadTickerData: (ticker: string) => {
    const t = ticker.toUpperCase();
    // Seed data provides instant baseline for known tickers.
    // For unknown tickers, start with a blank shell.
    // In both cases, live tool results (via processToolResult) overwrite seed values.
    const hasSeed = isSupported(t);
    set({
      activeTicker: t,
      companyData: hasSeed ? COMPANY_PROFILES[t] ?? blankCompany(t) : blankCompany(t),
      coverageData: hasSeed ? ANALYST_COVERAGE[t] ?? [] : [],
      consensusSummary: hasSeed ? CONSENSUS_SUMMARIES[t] ?? null : null,
      chartData: hasSeed ? CHART_DATA[t] ?? [] : [],
      filings: hasSeed ? SAMPLE_FILINGS[t] ?? [] : [],
      valuationData: hasSeed ? VALUATION_SNAPSHOTS[t] ?? null : null,
      sentimentData: hasSeed ? SENTIMENT_SNAPSHOTS[t] ?? null : null,
      activeTab: 'company',
      filingFilter: 'All',
      chartMetric: 'revenue',
    });
  },

  /* ── Pipeline ── */
  pipelineStages: defaultPipelineStages(),
  currentStageId: null,
  hitlGate: null,

  approveHitlGate: () => {
    const { hitlGate, pipelineStages, currentStageId } = get();
    if (!hitlGate) return;
    const updatedStages = pipelineStages.map((s) =>
      s.id === hitlGate.stageId ? { ...s, status: 'completed' as const, endTime: new Date() } : s,
    );
    const nextId = currentStageId ? currentStageId + 1 : null;
    set({
      hitlGate: null,
      pipelineStages: updatedStages,
      currentStageId: nextId,
    });
  },

  rejectHitlGate: () => {
    const { hitlGate, pipelineStages } = get();
    if (!hitlGate) return;
    const updatedStages = pipelineStages.map((s) =>
      s.id === hitlGate.stageId ? { ...s, status: 'failed' as const, endTime: new Date() } : s,
    );
    set({
      hitlGate: null,
      pipelineStages: updatedStages,
      currentStageId: null,
    });
  },

  /* ── Tool Events ── */
  toolEvents: [...DEMO_TOOL_EVENTS],

  /* ── Brief ── */
  briefData: null,

  /* ── Trace Panel ── */
  traceExpanded: false,
  toggleTrace: () => set((s) => ({ traceExpanded: !s.traceExpanded })),
}));

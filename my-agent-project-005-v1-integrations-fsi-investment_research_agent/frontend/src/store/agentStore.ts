/**
 * Zustand store — single source of truth for agent state.
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
  FinancialStatement,
  ChartMetric,
  FilingFilter,
} from '../types';
import * as agentApi from '../services/agentApi';
import {
  COMPANY_PROFILES,
  ANALYST_COVERAGE,
  CONSENSUS_SUMMARIES,
  CHART_DATA,
  SAMPLE_FILINGS,
  VALUATION_SNAPSHOTS,
  SENTIMENT_SNAPSHOTS,
  HISTORICAL_FINANCIALS,
  isSupported,
} from '../data/seedData';

interface AgentState {
  /* ── Auth ── */
  accessToken: string | null;
  instanceUrl: string | null;
  userInfo: UserInfo | null;
  setAuth: (token: string, instanceUrl: string, user: UserInfo) => void;
  clearAuth: () => void;

  /* ── Session ── */
  sessionId: string | null;
  sequenceId: number;
  isStreaming: boolean;
  error: string | null;
  startNewSession: () => Promise<void>;

  /* ── Chat ── */
  messages: Message[];
  sendMessage: (text: string) => Promise<void>;
  clearMessages: () => void;

  /* ── Research Data ── */
  activeTab: ResearchTab;
  setActiveTab: (tab: ResearchTab) => void;
  companyData: CompanyData | null;
  coverageData: CoverageData[];
  chartData: ChartDataPoint[];
  filings: FilingData[];
  setCompanyData: (data: CompanyData | null) => void;
  setCoverageData: (data: CoverageData[]) => void;
  setChartData: (data: ChartDataPoint[]) => void;
  setFilings: (data: FilingData[]) => void;

  /* ── Enhanced Research Data (v2) ── */
  activeTicker: string | null;
  consensusSummary: ConsensusSummary | null;
  valuationData: ValuationData | null;
  sentimentData: SentimentData | null;
  financialStatements: FinancialStatement[];
  chartMetric: ChartMetric;
  filingFilter: FilingFilter;
  setChartMetric: (metric: ChartMetric) => void;
  setFilingFilter: (filter: FilingFilter) => void;
  loadTickerData: (ticker: string) => void;

  /* ── Trace Panel ── */
  traceExpanded: boolean;
  toggleTrace: () => void;
}

const AGENT_ID = import.meta.env.VITE_SF_AGENT_ID || '';


function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  /* ── Auth ── */
  accessToken: null,
  instanceUrl: null,
  userInfo: null,
  setAuth: (token, instanceUrl, user) =>
    set({ accessToken: token, instanceUrl, userInfo: user }),
  clearAuth: () =>
    set({ accessToken: null, instanceUrl: null, userInfo: null, sessionId: null }),

  /* ── Session ── */
  sessionId: null,
  sequenceId: 0,
  isStreaming: false,
  error: null,

  startNewSession: async () => {
    const { accessToken, instanceUrl } = get();
    if (!accessToken || !instanceUrl) return;
    try {
      const sessionId = await agentApi.startSession(accessToken, instanceUrl, AGENT_ID);
      set({ sessionId, sequenceId: 0, messages: [], error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  /* ── Chat ── */
  messages: [],

  sendMessage: async (text: string) => {
    const { accessToken, instanceUrl, sessionId, sequenceId } = get();
    if (!accessToken || !instanceUrl || !sessionId) return;

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

    const nextSeq = sequenceId + 1;
    set((s) => ({
      messages: [...s.messages, userMsg, agentMsg],
      sequenceId: nextSeq,
      isStreaming: true,
      error: null,
    }));

    try {
      await agentApi.sendStreamingMessage(
        accessToken,
        instanceUrl,
        sessionId,
        text,
        nextSeq,
        (chunk: string) => {
          set((s) => {
            const msgs = [...s.messages];
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'agent') {
              msgs[msgs.length - 1] = { ...last, text: last.text + chunk };
            }
            return { messages: msgs };
          });
        },
        () => {
          set((s) => {
            const msgs = [...s.messages];
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'agent') {
              msgs[msgs.length - 1] = { ...last, isStreaming: false };
            }
            return { messages: msgs, isStreaming: false };
          });
        },
      );
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

  clearMessages: () => set({ messages: [] }),

  /* ── Research Data ── */
  activeTab: 'company',
  setActiveTab: (tab) => set({ activeTab: tab }),
  companyData: null,
  coverageData: [],
  chartData: [],
  filings: [],
  setCompanyData: (data) => set({ companyData: data }),
  setCoverageData: (data) => set({ coverageData: data }),
  setChartData: (data) => set({ chartData: data }),
  setFilings: (data) => set({ filings: data }),

  /* ── Enhanced Research Data (v2) ── */
  activeTicker: null,
  consensusSummary: null,
  valuationData: null,
  sentimentData: null,
  financialStatements: [],
  chartMetric: 'revenue',
  filingFilter: 'All',
  setChartMetric: (metric) => set({ chartMetric: metric }),
  setFilingFilter: (filter) => set({ filingFilter: filter }),
  loadTickerData: (ticker: string) => {
    const t = ticker.toUpperCase();
    if (!isSupported(t)) return;
    set({
      activeTicker: t,
      companyData: COMPANY_PROFILES[t] ?? null,
      coverageData: ANALYST_COVERAGE[t] ?? [],
      consensusSummary: CONSENSUS_SUMMARIES[t] ?? null,
      chartData: CHART_DATA[t] ?? [],
      filings: SAMPLE_FILINGS[t] ?? [],
      valuationData: VALUATION_SNAPSHOTS[t] ?? null,
      sentimentData: SENTIMENT_SNAPSHOTS[t] ?? null,
      financialStatements: HISTORICAL_FINANCIALS[t] ?? [],
      activeTab: 'company',
      filingFilter: 'All',
      chartMetric: 'revenue',
    });
  },

  /* ── Trace Panel ── */
  traceExpanded: false,
  toggleTrace: () => set((s) => ({ traceExpanded: !s.traceExpanded })),
}));

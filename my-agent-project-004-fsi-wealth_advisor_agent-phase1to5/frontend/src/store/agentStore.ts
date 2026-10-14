/**
 * Zustand store — single source of truth for wealth advisor agent state.
 * No seed data — this agent queries Data Cloud live.
 */

import { create } from 'zustand';
import type { Message, AdvisorTab, UserInfo } from '../types';
import * as agentApi from '../services/agentApi';
import { extractClientName, detectRelevantTab } from '../services/responseParser';

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

  /* ── Advisor Panel ── */
  activeTab: AdvisorTab;
  setActiveTab: (tab: AdvisorTab) => void;
  activeName: string | null;
  setActiveName: (name: string | null) => void;
  tabResponses: Record<AdvisorTab, string>;
  lastQueryTab: AdvisorTab | null;

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
      set({ sessionId, sequenceId: 0, messages: [], error: null, activeName: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  /* ── Chat ── */
  messages: [],

  sendMessage: async (text: string) => {
    const { accessToken, instanceUrl, sessionId, sequenceId } = get();
    if (!accessToken || !instanceUrl || !sessionId) return;

    // Auto-detect tab from user query
    const detectedTab = detectRelevantTab(text) || 'clients';
    set({ activeTab: detectedTab, lastQueryTab: detectedTab });

    // Try to extract client name from query
    const clientName = extractClientName(text);
    if (clientName) set({ activeName: clientName });

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
            let finalText = '';
            if (last && last.role === 'agent') {
              finalText = last.text;
              msgs[msgs.length - 1] = { ...last, isStreaming: false };
            }
            // Route completed response to the correct tab
            const tab = s.lastQueryTab || 'clients';
            const updatedTabResponses = { ...s.tabResponses };
            if (finalText && !finalText.startsWith('Error:')) {
              updatedTabResponses[tab] = finalText;
            }
            return { messages: msgs, isStreaming: false, tabResponses: updatedTabResponses };
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

  /* ── Advisor Panel ── */
  activeTab: 'clients',
  setActiveTab: (tab) => set({ activeTab: tab }),
  activeName: null,
  setActiveName: (name) => set({ activeName: name }),
  tabResponses: { clients: '', portfolio: '', goals: '', activity: '' },
  lastQueryTab: null,

  /* ── Trace Panel ── */
  traceExpanded: false,
  toggleTrace: () => set((s) => ({ traceExpanded: !s.traceExpanded })),
}));

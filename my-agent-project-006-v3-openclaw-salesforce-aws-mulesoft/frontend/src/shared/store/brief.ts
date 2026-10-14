/**
 * Zustand store for the in-flight brief being composed on Sarah's screen.
 *
 * Two parallel channels arrive over the WebSocket:
 *   - `brief_delta` events on the text channel
 *   - `citation` events on the citation channel
 * plus tool-call spans for the audit strip. All three merge here; components
 * read a consistent view. Stitching by span_id happens at render time.
 */

import { create } from 'zustand';
import type { Citation, ChartIntent, ToolCall } from '../types/api';

export interface BriefState {
  turnId: string | null;
  markdown: string;
  citationsBySpan: Record<string, Citation>;
  charts: ChartIntent[];
  toolCalls: ToolCall[];
  isStreaming: boolean;
  costTokens: number;
  costUsd: number;
  durationMs: number;

  startTurn: (turnId: string) => void;
  appendDelta: (spanId: string, delta: string) => void;
  addCitation: (c: Citation) => void;
  addChart: (c: ChartIntent) => void;
  addToolCall: (t: ToolCall) => void;
  endToolCall: (spanId: string, status: 'ok' | 'error', latencyMs: number) => void;
  completeTurn: (p: { costTokens: number; costUsd: number; durationMs: number }) => void;
  reset: () => void;
}

const INITIAL = {
  turnId: null,
  markdown: '',
  citationsBySpan: {},
  charts: [] as ChartIntent[],
  toolCalls: [] as ToolCall[],
  isStreaming: false,
  costTokens: 0,
  costUsd: 0,
  durationMs: 0,
};

export const useBriefStore = create<BriefState>((set) => ({
  ...INITIAL,
  startTurn: (turnId) =>
    set({
      ...INITIAL,
      turnId,
      isStreaming: true,
    }),
  appendDelta: (_spanId, delta) => set((s) => ({ markdown: s.markdown + delta })),
  addCitation: (c) =>
    set((s) => ({
      citationsBySpan: { ...s.citationsBySpan, [c.span_id]: c },
    })),
  addChart: (c) => set((s) => ({ charts: [...s.charts, c] })),
  addToolCall: (t) => set((s) => ({ toolCalls: [...s.toolCalls, t] })),
  endToolCall: (spanId, status, latencyMs) =>
    set((s) => ({
      toolCalls: s.toolCalls.map((t) =>
        t.span_id === spanId
          ? { ...t, status, latency_ms: latencyMs, completed_at: new Date().toISOString() }
          : t,
      ),
    })),
  completeTurn: ({ costTokens, costUsd, durationMs }) =>
    set({ isStreaming: false, costTokens, costUsd, durationMs }),
  reset: () => set({ ...INITIAL }),
}));

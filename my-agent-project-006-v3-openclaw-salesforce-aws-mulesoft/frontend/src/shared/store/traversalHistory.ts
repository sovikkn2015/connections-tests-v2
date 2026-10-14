/**
 * Bounded ring buffer of finished turns, rendered as the v1-style collapsible
 * end-to-end trace list under the chat pane.
 */

import { create } from 'zustand';
import type { ToolCall } from '../types/api';

export interface TraversalHistoryEntry {
  turnId: string;
  text: string;
  startedAt: number;
  endedAt: number;
  toolCount: number;
  mcpsTouched: string[];
  toolCalls: ToolCall[];
  gateTrace: Array<{ gate: string; status: string; ts: number }>;
  durationMs: number;
  costUsd?: number;
  costTokens?: number;
  langfuseTraceId?: string;
}

export interface TraversalHistoryState {
  entries: TraversalHistoryEntry[];
  expandedTurnId: string | null;
  maxEntries: number;

  appendFromCurrentTurn: (entry: TraversalHistoryEntry) => void;
  toggleExpand: (turnId: string) => void;
  clear: () => void;
}

const DEFAULT_MAX_ENTRIES = 20;

export const useTraversalHistoryStore = create<TraversalHistoryState>((set) => ({
  entries: [],
  expandedTurnId: null,
  maxEntries: DEFAULT_MAX_ENTRIES,

  appendFromCurrentTurn: (entry) =>
    set((s) => {
      // Replace if turnId already exists (late-arriving refine of a turn),
      // else append; then trim to the max size keeping newest.
      const withoutDupe = s.entries.filter((e) => e.turnId !== entry.turnId);
      const next = [...withoutDupe, entry];
      const trimmed =
        next.length > s.maxEntries ? next.slice(next.length - s.maxEntries) : next;
      return { entries: trimmed };
    }),

  toggleExpand: (turnId) =>
    set((s) => ({ expandedTurnId: s.expandedTurnId === turnId ? null : turnId })),

  clear: () => set({ entries: [], expandedTurnId: null }),
}));

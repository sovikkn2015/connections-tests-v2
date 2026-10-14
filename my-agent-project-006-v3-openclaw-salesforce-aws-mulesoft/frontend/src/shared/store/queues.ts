/**
 * Zustand store for the RM's four queues (Inbox / Briefs / Alerts / Pending).
 * Items are pushed/updated/removed via WebSocket queue_update events and
 * rendered in the advisor screen's left panel.
 */

import { create } from 'zustand';
import type { AdvisorQueueKind, QueueItemSummary } from '../types/api';

export interface QueuesState {
  itemsByQueue: Record<AdvisorQueueKind, QueueItemSummary[]>;
  selectedItemId: string | null;

  setItems: (kind: AdvisorQueueKind, items: QueueItemSummary[]) => void;
  upsertItem: (item: QueueItemSummary) => void;
  removeItem: (kind: AdvisorQueueKind, id: string) => void;
  selectItem: (id: string | null) => void;
}

const EMPTY: Record<AdvisorQueueKind, QueueItemSummary[]> = {
  inbox: [],
  briefs: [],
  alerts: [],
  pending: [],
};

export const useQueuesStore = create<QueuesState>((set) => ({
  itemsByQueue: EMPTY,
  selectedItemId: null,
  setItems: (kind, items) =>
    set((s) => ({ itemsByQueue: { ...s.itemsByQueue, [kind]: items } })),
  upsertItem: (item) =>
    set((s) => {
      const existing = s.itemsByQueue[item.kind];
      const idx = existing.findIndex((x) => x.id === item.id);
      const next = idx >= 0 ? existing.map((x, i) => (i === idx ? item : x)) : [item, ...existing];
      return { itemsByQueue: { ...s.itemsByQueue, [item.kind]: next } };
    }),
  removeItem: (kind, id) =>
    set((s) => ({
      itemsByQueue: {
        ...s.itemsByQueue,
        [kind]: s.itemsByQueue[kind].filter((x) => x.id !== id),
      },
    })),
  selectItem: (id) => set({ selectedItemId: id }),
}));

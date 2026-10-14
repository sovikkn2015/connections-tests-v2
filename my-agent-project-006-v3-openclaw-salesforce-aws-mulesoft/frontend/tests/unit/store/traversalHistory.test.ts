/**
 * Unit tests for the bounded traversal history ring buffer.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  useTraversalHistoryStore,
  type TraversalHistoryEntry,
} from '../../../src/shared/store/traversalHistory';

function makeEntry(turnId: string, overrides: Partial<TraversalHistoryEntry> = {}): TraversalHistoryEntry {
  return {
    turnId,
    text: `query ${turnId}`,
    startedAt: 1000,
    endedAt: 1500,
    toolCount: 3,
    mcpsTouched: ['market-data'],
    toolCalls: [],
    gateTrace: [],
    durationMs: 500,
    costUsd: 0.001,
    costTokens: 500,
    ...overrides,
  };
}

describe('traversal history store', () => {
  beforeEach(() => {
    useTraversalHistoryStore.setState({
      entries: [],
      expandedTurnId: null,
      maxEntries: 20,
    });
  });

  it('appends an entry to the end of the buffer', () => {
    useTraversalHistoryStore.getState().appendFromCurrentTurn(makeEntry('t1'));
    useTraversalHistoryStore.getState().appendFromCurrentTurn(makeEntry('t2'));
    const entries = useTraversalHistoryStore.getState().entries;
    expect(entries.map((e) => e.turnId)).toEqual(['t1', 't2']);
  });

  it('evicts the oldest entry when maxEntries is exceeded (ring buffer)', () => {
    useTraversalHistoryStore.setState({ maxEntries: 3 });
    const append = useTraversalHistoryStore.getState().appendFromCurrentTurn;
    append(makeEntry('a'));
    append(makeEntry('b'));
    append(makeEntry('c'));
    append(makeEntry('d'));
    const ids = useTraversalHistoryStore.getState().entries.map((e) => e.turnId);
    expect(ids).toEqual(['b', 'c', 'd']);
  });

  it('toggleExpand is idempotent when called twice on the same turnId', () => {
    const { toggleExpand } = useTraversalHistoryStore.getState();
    toggleExpand('x');
    expect(useTraversalHistoryStore.getState().expandedTurnId).toBe('x');
    toggleExpand('x');
    expect(useTraversalHistoryStore.getState().expandedTurnId).toBeNull();
  });

  it('clear() empties the buffer and collapses any expansion', () => {
    const s = useTraversalHistoryStore.getState();
    s.appendFromCurrentTurn(makeEntry('k'));
    s.toggleExpand('k');
    s.clear();
    const next = useTraversalHistoryStore.getState();
    expect(next.entries).toEqual([]);
    expect(next.expandedTurnId).toBeNull();
  });

  it('preserves insertion order across many appends', () => {
    const append = useTraversalHistoryStore.getState().appendFromCurrentTurn;
    for (let i = 0; i < 10; i++) {
      append(makeEntry(`turn-${i}`, { startedAt: i * 1000 }));
    }
    const ids = useTraversalHistoryStore.getState().entries.map((e) => e.turnId);
    expect(ids).toEqual([
      'turn-0',
      'turn-1',
      'turn-2',
      'turn-3',
      'turn-4',
      'turn-5',
      'turn-6',
      'turn-7',
      'turn-8',
      'turn-9',
    ]);
  });

  it('replaces an existing entry when the same turnId is appended twice', () => {
    const append = useTraversalHistoryStore.getState().appendFromCurrentTurn;
    append(makeEntry('dup', { text: 'first' }));
    append(makeEntry('dup', { text: 'refined' }));
    const entries = useTraversalHistoryStore.getState().entries;
    expect(entries).toHaveLength(1);
    expect(entries[0]!.text).toBe('refined');
  });
});

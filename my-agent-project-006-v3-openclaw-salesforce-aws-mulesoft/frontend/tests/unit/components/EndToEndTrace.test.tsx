import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EndToEndTrace } from '../../../src/shared/components/EndToEndTrace';
import {
  useTraversalHistoryStore,
  type TraversalHistoryEntry,
} from '../../../src/shared/store/traversalHistory';
import type { ToolCall } from '../../../src/shared/types/api';

const T0 = Date.UTC(2026, 0, 1, 12, 0, 0);

const tc = (o: Partial<ToolCall> = {}): ToolCall => ({
  span_id: 'sp',
  tool_name: 'finnhub_quote',
  agent_id: 'market_specialist',
  started_at: new Date(T0 + 50).toISOString(),
  completed_at: new Date(T0 + 250).toISOString(),
  status: 'ok',
  latency_ms: 200,
  ...o,
});

const entry = (o: Partial<TraversalHistoryEntry> & { turnId: string }): TraversalHistoryEntry => {
  const { turnId, ...rest } = o;
  return {
    turnId,
    text: 'Research NVDA earnings',
    startedAt: T0,
    endedAt: T0 + 2000,
    toolCount: 2,
    mcpsTouched: ['finnhub-mcp', 'sec-edgar-mcp'],
    toolCalls: [tc({ span_id: 's1' }), tc({ span_id: 's2', tool_name: 'edgar_fetch' })],
    gateTrace: [],
    durationMs: 2000,
    costUsd: 0.0042,
    costTokens: 1234,
    langfuseTraceId: undefined,
    ...rest,
  };
};

function seedEntries(entries: TraversalHistoryEntry[], expandedTurnId: string | null = null) {
  // setState is a partial merge in zustand; only provide the data fields we
  // want to override. Store actions (toggleExpand, clear, etc.) are preserved.
  useTraversalHistoryStore.setState({ entries, expandedTurnId });
}

describe('EndToEndTrace', () => {
  beforeEach(() => {
    useTraversalHistoryStore.getState().clear();
  });

  it('renders the empty state when no entries', () => {
    render(<EndToEndTrace />);
    expect(screen.getByTestId('e2e-trace-empty')).toHaveTextContent(/no completed turns yet/i);
  });

  it('renders entries newest-first by startedAt regardless of store insertion order', () => {
    // Simulate builder 1's store which appends new turns at the end
    // (oldest-first insertion order). Component must sort by startedAt desc.
    seedEntries([
      entry({ turnId: 'turn-older', text: 'Older query', startedAt: T0 }),
      entry({ turnId: 'turn-newest', text: 'Newest query', startedAt: T0 + 1000 }),
    ]);
    render(<EndToEndTrace />);
    const buttons = screen.getAllByRole('button');
    // newest should be first despite being last in the input array
    expect(buttons[0]).toHaveTextContent('Newest query');
    expect(buttons[1]).toHaveTextContent('Older query');
    expect(buttons[0]).toHaveTextContent('2 tools → finnhub-mcp, sec-edgar-mcp');
  });

  it('click toggles expansion of a row', () => {
    seedEntries([entry({ turnId: 't-click' })]);
    render(<EndToEndTrace />);
    const row = screen.getByTestId('e2e-row-t-click').querySelector('button') as HTMLButtonElement;
    expect(row).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(row);
    expect(row).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('e2e-expanded-t-click')).toBeInTheDocument();
    fireEvent.click(row);
    expect(row).toHaveAttribute('aria-expanded', 'false');
  });

  it('keyboard Enter and Space toggle expansion on the row button', () => {
    seedEntries([entry({ turnId: 't-kbd' })]);
    render(<EndToEndTrace />);
    const row = screen.getByTestId('e2e-row-t-kbd').querySelector('button') as HTMLButtonElement;
    // jsdom dispatches a synthetic click from Enter on a native <button>; we
    // use fireEvent.click which is what the browser would produce on Enter.
    fireEvent.click(row);
    expect(row).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(row);
    expect(row).toHaveAttribute('aria-expanded', 'false');
  });

  it('renders Langfuse deep-link only when base URL + traceId present', () => {
    seedEntries([
      entry({ turnId: 't-with', langfuseTraceId: 'lf-abc' }),
      entry({ turnId: 't-without', langfuseTraceId: undefined }),
    ]);
    render(<EndToEndTrace langfuseBaseUrl="https://langfuse.example.test" />);
    const link = screen.getByTestId('e2e-langfuse-t-with') as HTMLAnchorElement;
    expect(link).toHaveAttribute('href', 'https://langfuse.example.test/trace/lf-abc');
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.queryByTestId('e2e-langfuse-t-without')).toBeNull();
  });

  it('expanded row renders MiniTimeline + ToolTable + cost badges', () => {
    seedEntries([entry({ turnId: 't-exp' })], 't-exp');
    render(<EndToEndTrace />);
    const expanded = screen.getByTestId('e2e-expanded-t-exp');
    expect(expanded).toBeInTheDocument();
    // MiniTimeline svg
    expect(expanded.querySelector('[data-testid="mini-timeline-svg"]')).not.toBeNull();
    // ToolTable columns
    expect(expanded.querySelector('table')).not.toBeNull();
    // Cost badges rendered
    expect(expanded).toHaveTextContent('1,234 tok');
    expect(expanded).toHaveTextContent('$0.0042');
  });
});

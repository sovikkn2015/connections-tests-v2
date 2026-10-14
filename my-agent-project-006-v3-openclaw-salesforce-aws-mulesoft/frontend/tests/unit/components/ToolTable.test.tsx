import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ToolTable } from '../../../src/shared/components/ToolTable';
import type { ToolCall } from '../../../src/shared/types/api';

const baseCall = (o: Partial<ToolCall>): ToolCall => ({
  span_id: 's1',
  tool_name: 'finnhub_quote',
  agent_id: 'market_specialist',
  started_at: '2026-01-01T12:00:00.000Z',
  completed_at: '2026-01-01T12:00:00.200Z',
  status: 'ok',
  latency_ms: 200,
  ...o,
});

describe('ToolTable', () => {
  it('renders canonical column headers', () => {
    render(<ToolTable toolCalls={[baseCall({})]} />);
    for (const header of ['Tool', 'MCP Server', 'Data Source', 'Status', 'Duration', 'Span']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument();
    }
  });

  it('renders the correct glyph and label per status', () => {
    const calls: ToolCall[] = [
      baseCall({ span_id: 'ok1', status: 'ok' }),
      baseCall({ span_id: 'err1', status: 'error', latency_ms: 400 }),
      baseCall({ span_id: 'run1', status: 'running', latency_ms: undefined, completed_at: undefined }),
    ];
    render(<ToolTable toolCalls={calls} />);
    expect(screen.getByTestId('tool-row-ok1')).toHaveAttribute('data-status', 'ok');
    expect(screen.getByTestId('tool-row-ok1')).toHaveTextContent('✓ OK');
    expect(screen.getByTestId('tool-row-err1')).toHaveTextContent('⨯ Error');
    expect(screen.getByTestId('tool-row-run1')).toHaveTextContent('… Running');
  });

  it('formats durations in ms or s', () => {
    const calls: ToolCall[] = [
      baseCall({ span_id: 's-ms', latency_ms: 340 }),
      baseCall({ span_id: 's-sec', latency_ms: 2340 }),
      baseCall({ span_id: 's-none', latency_ms: undefined, completed_at: undefined, status: 'running' }),
    ];
    render(<ToolTable toolCalls={calls} />);
    expect(screen.getByTestId('tool-row-s-ms')).toHaveTextContent('340ms');
    expect(screen.getByTestId('tool-row-s-sec')).toHaveTextContent('2.34s');
    expect(screen.getByTestId('tool-row-s-none')).toHaveTextContent('—');
  });

  it('shows empty placeholder when no calls', () => {
    render(<ToolTable toolCalls={[]} />);
    expect(screen.getByRole('note')).toHaveTextContent(/no tool calls/i);
  });
});

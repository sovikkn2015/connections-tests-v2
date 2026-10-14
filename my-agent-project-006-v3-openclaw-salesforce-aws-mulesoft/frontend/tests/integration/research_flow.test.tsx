/**
 * Integration: Sarah's research terminal. Streams a brief with citation
 * markers, hydrates chips, and opens the source drill-down pane.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { ResearchTerminal } from '../../src/v1/personas/research/ResearchTerminal';
import { RestClient } from '../../src/shared/lib/restClient';
import { useSessionStore } from '../../src/shared/store/session';
import { useBriefStore } from '../../src/shared/store/brief';
import { MockWebSocket } from '../mocks/mockWebSocket';
import { createStubFetch } from '../mocks/restStub';

function makeRest(): RestClient {
  return new RestClient('https://api.example.test', () => 'tok', createStubFetch());
}

describe('ResearchTerminal flow', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    useBriefStore.getState().reset();
    useSessionStore.setState({
      sessionToken: 'tok',
      principalId: 'sarah',
      principalName: 'Sarah Chen',
      persona: 'fsi_research',
      sessionId: 'sess',
      correlationId: 'corr-abcd',
      connectionStatus: 'idle',
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it('renders with query input and audit strip', async () => {
    render(<ResearchTerminal rest={makeRest()} />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });
    expect(screen.getByLabelText(/research query/i)).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /audit trace/i })).toBeInTheDocument();
  });

  it('submits a turn and streams the brief with citation chips', async () => {
    render(<ResearchTerminal rest={makeRest()} />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const input = screen.getByLabelText(/research query/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Research NVDA earnings' } });
    fireEvent.keyDown(input, { key: 'Enter', metaKey: true });

    const sentTurn = MockWebSocket.last!.sent
      .map((s) => JSON.parse(s))
      .find((m) => m.type === 'turn');
    expect(sentTurn).toBeTruthy();
    expect(sentTurn.text).toBe('Research NVDA earnings');

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'turn_started',
        turn_id: sentTurn.turn_id,
        agent_id: 'research_orchestrator',
      });
      MockWebSocket.last!.simulateMessage({
        type: 'brief_delta',
        turn_id: sentTurn.turn_id,
        span_id: 's1',
        delta: 'NVDA datacenter grew 143% YoY',
      });
      MockWebSocket.last!.simulateMessage({
        type: 'brief_delta',
        turn_id: sentTurn.turn_id,
        span_id: 's1',
        delta: '[src:s1].',
      });
      MockWebSocket.last!.simulateMessage({
        type: 'citation',
        turn_id: sentTurn.turn_id,
        citation: {
          span_id: 's1',
          source_id: 'nvda_item7',
          source_type: 'filing',
          label: 'NVDA 10-K Item 7',
          page: 42,
        },
      });
    });

    expect(screen.getByText(/NVDA datacenter grew 143% YoY/i)).toBeInTheDocument();
    const chip = await screen.findByTestId('chip-s1');
    expect(chip).toHaveAttribute('data-pending', 'false');
    expect(chip).toHaveTextContent('NVDA 10-K Item 7');
  });

  it('opens the source drill-down pane when a citation chip is clicked', async () => {
    render(<ResearchTerminal rest={makeRest()} />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'turn_started',
        turn_id: 'tid-1',
        agent_id: 'research_orchestrator',
      });
      MockWebSocket.last!.simulateMessage({
        type: 'brief_delta',
        turn_id: 'tid-1',
        span_id: 'sX',
        delta: 'Risk disclosed[src:sX].',
      });
      MockWebSocket.last!.simulateMessage({
        type: 'citation',
        turn_id: 'tid-1',
        citation: {
          span_id: 'sX',
          source_id: 'chunk-1',
          source_type: 'filing',
          label: '10-K Item 1A',
          page: 12,
        },
      });
    });

    const chip = await screen.findByTestId('chip-sX');
    await act(async () => {
      chip.click();
    });

    await waitFor(() => {
      expect(screen.getByRole('region', { name: /source drill-down/i })).toBeInTheDocument();
    });
  });
});

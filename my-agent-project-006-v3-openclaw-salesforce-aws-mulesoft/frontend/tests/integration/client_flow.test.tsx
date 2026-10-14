/**
 * Integration: client channel. WhatsApp-style bubbles, permanent disclaimer,
 * CTA buttons. MNPI-free by contract; we verify the UI contracts here.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ClientChannel } from '../../src/v1/personas/client/ClientChannel';
import { useSessionStore } from '../../src/shared/store/session';
import { MockWebSocket } from '../mocks/mockWebSocket';

describe('ClientChannel flow', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    useSessionStore.setState({
      sessionToken: 'tok',
      principalId: 'client-1',
      principalName: 'Client User',
      persona: 'fsi_client_liaison',
      sessionId: 'sess',
      correlationId: 'corr',
      connectionStatus: 'idle',
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it('shows permanent disclaimer and CTA buttons', () => {
    render(<ClientChannel />);
    expect(
      screen.getByText(/For informational purposes\. Your RM makes recommendations\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /schedule call/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask rm/i })).toBeInTheDocument();
  });

  it('sends the client turn over WebSocket on submit', async () => {
    render(<ClientChannel />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const input = screen.getByLabelText(/message/i);
    fireEvent.change(input, { target: { value: 'Should I be worried about NVDA?' } });
    fireEvent.submit(input.closest('form')!);

    const sent = MockWebSocket.last!.sent.map((s) => JSON.parse(s));
    const turn = sent.find((m) => m.type === 'turn');
    expect(turn).toBeTruthy();
    expect(turn.text).toBe('Should I be worried about NVDA?');
  });

  it('Ask RM and Schedule call both emit turn messages', async () => {
    render(<ClientChannel />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    fireEvent.click(screen.getByRole('button', { name: /schedule call/i }));
    fireEvent.click(screen.getByRole('button', { name: /ask rm/i }));
    const turns = MockWebSocket.last!.sent
      .map((s) => JSON.parse(s))
      .filter((m) => m.type === 'turn');
    expect(turns).toHaveLength(2);
    expect(turns[0].text).toMatch(/schedule/i);
    expect(turns[1].text).toMatch(/connect me/i);
  });
});

/**
 * Component tests for the RM Alert Queue. Drives the component via an
 * injected fetch stub so the test has no reliance on MSW or a live backend.
 *
 * NOTE on location: the spec called for `src/personas/advisor/__tests__/AlertQueue.test.tsx`
 * but the project's vitest config scans only `tests/**` (see vite.config.ts).
 * Placed here to be runnable under the existing npm test command without
 * modifying vite.config.ts.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AlertQueue, type AlertInquiry } from '../../../src/v1/personas/advisor/AlertQueue';
import { useSessionStore } from '../../../src/shared/store/session';

function buildFetchReturning(items: AlertInquiry[]): typeof fetch {
  return (async (input: RequestInfo | URL): Promise<Response> => {
    const url = typeof input === 'string' ? input : input.toString();
    if (url.includes('/api/inquiries')) {
      return new Response(JSON.stringify({ items }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('Not Found', { status: 404 });
  }) as unknown as typeof fetch;
}

describe('AlertQueue', () => {
  beforeEach(() => {
    useSessionStore.setState({
      sessionToken: 'test-token',
      principalId: 'rm-test',
      principalName: 'RM Test',
      persona: 'fsi_advisor',
      sessionId: 'sess-1',
      correlationId: 'corr-1',
      connectionStatus: 'open',
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    useSessionStore.getState().clearAuth();
  });

  it('renders empty state when no alerts', async () => {
    const fetchFn = buildFetchReturning([]);
    render(<AlertQueue fetchFn={fetchFn} pollIntervalMs={60_000} />);
    await waitFor(() => {
      expect(screen.getByTestId('alert-queue-empty')).toBeInTheDocument();
    });
    expect(screen.getByText(/No active volatility alerts/i)).toBeInTheDocument();
  });

  it('renders alert rows with ticker and concentration', async () => {
    const items: AlertInquiry[] = [
      {
        id: 'inq-1',
        ticker: 'NVDA',
        concentration_pct: 18.47,
        client_name: 'Patel Household',
        client_contact_id: '003000000000001',
        auto_send_eligible: true,
        timestamp: '2025-03-04T14:22:00.000Z',
      },
      {
        id: 'inq-2',
        ticker: 'TSLA',
        concentration_pct: 9.12,
        client_name: 'Okafor Household',
        client_contact_id: '003000000000002',
        auto_send_eligible: false,
        timestamp: '2025-03-04T14:24:00.000Z',
      },
    ];
    const fetchFn = buildFetchReturning(items);
    render(<AlertQueue fetchFn={fetchFn} pollIntervalMs={60_000} />);
    await waitFor(() => {
      expect(screen.getByTestId('alert-queue-list')).toBeInTheDocument();
    });
    const row1 = screen.getByTestId('alert-row-inq-1');
    const row2 = screen.getByTestId('alert-row-inq-2');
    expect(row1).toHaveAttribute('data-ticker', 'NVDA');
    expect(row1).toHaveTextContent('NVDA');
    expect(row1).toHaveTextContent('18.47%');
    expect(row2).toHaveAttribute('data-ticker', 'TSLA');
    expect(row2).toHaveTextContent('TSLA');
    expect(row2).toHaveTextContent('9.12%');
  });

  it('shows an error banner when the API fails', async () => {
    const fetchFn = (async () =>
      new Response('boom', { status: 500 })) as unknown as typeof fetch;
    render(<AlertQueue fetchFn={fetchFn} pollIntervalMs={60_000} />);
    await waitFor(() => {
      expect(screen.getByTestId('alert-queue-error')).toBeInTheDocument();
    });
  });

  it('polls on interval', async () => {
    let calls = 0;
    const fetchFn = (async (input: RequestInfo | URL): Promise<Response> => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/inquiries')) {
        calls += 1;
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('Not Found', { status: 404 });
    }) as unknown as typeof fetch;
    render(<AlertQueue fetchFn={fetchFn} pollIntervalMs={5_000} />);
    await waitFor(() => {
      expect(calls).toBeGreaterThanOrEqual(1);
    });
    const initial = calls;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_001);
    });
    expect(calls).toBeGreaterThan(initial);
  });
});

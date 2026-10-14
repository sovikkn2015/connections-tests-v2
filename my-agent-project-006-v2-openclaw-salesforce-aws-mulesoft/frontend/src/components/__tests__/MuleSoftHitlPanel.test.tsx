/**
 * Unit tests for MuleSoftHitlPanel.
 *
 * The component is a pure consumer of useAgentStore. We mock the hook to
 * return controlled gate shapes and assert the 5 required behaviors:
 *   1. renders null when no gate is present
 *   2. renders the action badge + summary when a gate is present
 *   3. Approve button is disabled once the countdown elapses
 *   4. Reject 'Confirm reject' button is disabled unless a note is typed
 *   5. the 5-minute countdown eventually fires markHitlTimedOut
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, cleanup, fireEvent } from '@testing-library/react';
import MuleSoftHitlPanel from '../MuleSoftHitlPanel';
import type { HitlPendingGate } from '../../types';

// --- mock the zustand hook ------------------------------------------------

type StoreShape = {
  hitlPendingGate: HitlPendingGate | null;
  approveHitlPending: ReturnType<typeof vi.fn>;
  rejectHitlPending: ReturnType<typeof vi.fn>;
  markHitlTimedOut: ReturnType<typeof vi.fn>;
};

let storeState: StoreShape;

vi.mock('../../store/agentStore', () => ({
  useAgentStore: () => storeState,
}));

function buildGate(overrides: Partial<HitlPendingGate['event']> = {}, status: HitlPendingGate['status'] = 'waiting_first'): HitlPendingGate {
  const expiresAt = Math.floor(Date.now() / 1000) + 300; // 5 min
  return {
    status,
    event: {
      type: 'hitl.pending',
      token_hash: 'a1b2c3d4e5f67890'.repeat(2).slice(0, 64),
      plan_hash: '0123456789abcdef'.repeat(2).slice(0, 64),
      action: 'submit_order',
      summary_text: 'BUY 100 AAPL @ MARKET for Client Patel (~$17,500 notional)',
      requires_dual_auth: false,
      client_id: 'CLI-PATEL-001',
      account_id: 'ACC-PATEL-001',
      expires_at: expiresAt,
      plan_details: { ticker: 'AAPL', side: 'BUY', quantity: 100, order_type: 'MARKET' },
      ...overrides,
    },
  };
}

beforeEach(() => {
  storeState = {
    hitlPendingGate: null,
    approveHitlPending: vi.fn().mockResolvedValue(undefined),
    rejectHitlPending: vi.fn().mockResolvedValue(undefined),
    markHitlTimedOut: vi.fn(),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

// --- tests ----------------------------------------------------------------

describe('MuleSoftHitlPanel', () => {
  it('renders nothing when no gate is present', () => {
    storeState.hitlPendingGate = null;
    const { container } = render(<MuleSoftHitlPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders TRADE badge, summary, and client/account ids when a gate is present', () => {
    storeState.hitlPendingGate = buildGate();
    render(<MuleSoftHitlPanel />);

    expect(screen.getByText('TRADE')).toBeInTheDocument();
    expect(screen.getByText(/BUY 100 AAPL/)).toBeInTheDocument();
    expect(screen.getByText('CLI-PATEL-001')).toBeInTheDocument();
    expect(screen.getByText('ACC-PATEL-001')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve/i })).toBeEnabled();
  });

  it('disables the Approve button once the gate has expired', () => {
    vi.useFakeTimers();
    // Gate already expired 10 seconds ago.
    const expired = {
      ...buildGate(),
      event: { ...buildGate().event, expires_at: Math.floor(Date.now() / 1000) - 10 },
    };
    storeState.hitlPendingGate = expired;

    render(<MuleSoftHitlPanel />);
    // Let the countdown effect's first tick fire.
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText('EXPIRED')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve/i })).toBeDisabled();
  });

  it('requires a non-empty note before the Confirm reject button becomes enabled', () => {
    storeState.hitlPendingGate = buildGate();
    render(<MuleSoftHitlPanel />);

    // Step 1: open the reject note view
    fireEvent.click(screen.getByRole('button', { name: /Reject/i }));
    const confirmBtn = screen.getByRole('button', { name: /Confirm reject/i });
    expect(confirmBtn).toBeDisabled();

    // Step 2: type a note
    const note = screen.getByPlaceholderText(/Optional: explain the rationale/i);
    fireEvent.change(note, { target: { value: 'Insufficient justification.' } });
    expect(confirmBtn).toBeEnabled();
  });

  it('calls markHitlTimedOut when the countdown reaches 0', () => {
    vi.useFakeTimers();
    // Expires one second from now.
    const gate = {
      ...buildGate(),
      event: { ...buildGate().event, expires_at: Math.floor(Date.now() / 1000) + 1 },
    };
    storeState.hitlPendingGate = gate;

    render(<MuleSoftHitlPanel />);
    // Advance 2 seconds — past the expires_at.
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(storeState.markHitlTimedOut).toHaveBeenCalledWith(gate.event.token_hash);
  });
});

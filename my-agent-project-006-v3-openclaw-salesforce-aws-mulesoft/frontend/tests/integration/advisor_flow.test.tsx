/**
 * Integration: advisor screen. Drives the inbound event channel via a mock
 * WebSocket to light up the seven-gate tracker and exercise HITL approval.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AdvisorScreen } from '../../src/v1/personas/advisor/AdvisorScreen';
import { useSessionStore } from '../../src/shared/store/session';
import { useBriefStore } from '../../src/shared/store/brief';
import { useQueuesStore } from '../../src/shared/store/queues';
import { MockWebSocket } from '../mocks/mockWebSocket';
import type { ActionPlan } from '../../src/shared/types/api';

function resetStores() {
  useBriefStore.getState().reset();
  useSessionStore.getState().clearAuth();
  useQueuesStore.setState({
    itemsByQueue: { inbox: [], briefs: [], alerts: [], pending: [] },
    selectedItemId: null,
  });
  useSessionStore.setState({
    sessionToken: 'tok',
    principalId: 'rm-1',
    principalName: 'RM User',
    persona: 'fsi_advisor',
    sessionId: 'sess',
    correlationId: 'corr-1234',
    connectionStatus: 'idle',
  });
}

describe('AdvisorScreen flow', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    resetStores();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it('renders queues, conversation, and context panels', async () => {
    render(<AdvisorScreen />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });
    expect(screen.getByRole('tab', { name: /Inbox/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Advisor query/i)).toBeInTheDocument();
    expect(screen.getByText(/Client context/i)).toBeInTheDocument();
  });

  it('shows the seven-gate tracker when a hitl_prompt arrives', async () => {
    render(<AdvisorScreen />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const plan: ActionPlan = {
      plan_id: 'p1',
      plan_hash: 'abcdef1234567890',
      action_type: 'submit_order',
      summary: 'Sell 3,000 NVDA for Patel household',
      client_household: 'patel-001',
      notional_usd: 487_000,
      requires_dual_auth: false,
      gates: [],
    };

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'hitl_prompt',
        turn_id: 't1',
        plan,
        ttl_seconds: 300,
      });
    });

    expect(screen.getByText(/Approval required/i)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByTestId('gate-guardrails')).toHaveAttribute('data-status', 'pending');

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'gate_passed',
        turn_id: 't1',
        plan_id: 'p1',
        gate: 'guardrails',
        status: 'passed',
      });
    });

    expect(screen.getByTestId('gate-guardrails')).toHaveAttribute('data-status', 'passed');
  });

  it('emits hitl_approval on Approve click (optimistic)', async () => {
    render(<AdvisorScreen />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const plan: ActionPlan = {
      plan_id: 'p2',
      plan_hash: '9f87e6d5c4b3a2',
      action_type: 'initiate_wire',
      summary: 'Wire $150,000 to external bank',
      client_household: 'patel-001',
      notional_usd: 150_000,
      requires_dual_auth: true,
      gates: [],
    };

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'hitl_prompt',
        turn_id: 't2',
        plan,
        ttl_seconds: 300,
      });
    });

    const approve = screen.getByRole('button', { name: /Approve/i });
    await act(async () => {
      approve.click();
    });

    const sent = MockWebSocket.last!.sent.map((s) => JSON.parse(s));
    const approval = sent.find((m) => m.type === 'hitl_approval');
    expect(approval).toMatchObject({
      type: 'hitl_approval',
      plan_id: 'p2',
      plan_hash: '9f87e6d5c4b3a2',
      approved: true,
    });
  });
});



// ---------------------------------------------------------------------------
// Wave 2: P1.6 - useOptimisticApproval <-> gate-event reconciliation.
// ---------------------------------------------------------------------------

describe('AdvisorScreen HITL optimistic reconciliation', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    resetStores();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it('confirms the optimistic approval on gate_passed(hitl) and hides the rollback toast', async () => {
    render(<AdvisorScreen />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const plan: ActionPlan = {
      plan_id: 'p_opt_1',
      plan_hash: 'abcdef1234567890',
      action_type: 'submit_order',
      summary: 'Buy 100 AAPL',
      client_household: 'patel-001',
      notional_usd: 18_000,
      requires_dual_auth: false,
      gates: [],
    };

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'hitl_prompt',
        turn_id: 't_opt_1',
        plan,
        ttl_seconds: 300,
      });
    });

    const approve = screen.getByRole('button', { name: /Approve/i });
    await act(async () => {
      approve.click();
    });

    expect(screen.getByText(/validating/i)).toBeInTheDocument();

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'gate_passed',
        turn_id: 't_opt_1',
        plan_id: 'p_opt_1',
        gate: 'hitl',
        status: 'passed',
      });
    });

    expect(screen.queryByText(/validating/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('rolls back the optimistic approval on gate_failed(hitl) and shows a toast', async () => {
    render(<AdvisorScreen />);
    await act(async () => {
      MockWebSocket.last?.simulateOpen();
    });

    const plan: ActionPlan = {
      plan_id: 'p_opt_2',
      plan_hash: 'fedcba9876543210',
      action_type: 'initiate_wire',
      summary: 'Wire $150K',
      client_household: 'patel-001',
      notional_usd: 150_000,
      requires_dual_auth: true,
      gates: [],
    };

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'hitl_prompt',
        turn_id: 't_opt_2',
        plan,
        ttl_seconds: 300,
      });
    });

    const approve = screen.getByRole('button', { name: /Approve/i });
    await act(async () => {
      approve.click();
    });

    await act(async () => {
      MockWebSocket.last!.simulateMessage({
        type: 'gate_failed',
        turn_id: 't_opt_2',
        plan_id: 'p_opt_2',
        gate: 'hitl',
        status: 'failed',
        detail: 'token expired',
      });
    });

    const toast = screen.getByRole('alert');
    expect(toast).toHaveAttribute('data-tier', 'recoverable');
    expect(toast.textContent).toMatch(/Rolled back/i);
  });
});

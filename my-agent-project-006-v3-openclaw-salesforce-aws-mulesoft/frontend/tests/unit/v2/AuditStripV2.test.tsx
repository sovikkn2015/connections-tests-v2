/**
 * AuditStripV2 — per-specialist pills derived from live tool-calls, HITL-hold
 * indicator when gate ④ is in progress, right-aligned turn summary.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { AuditStripV2 } from '../../../src/v2/atoms/AuditStripV2';
import { useBriefStore } from '../../../src/shared/store/brief';
import { useSessionStore } from '../../../src/shared/store/session';
import { SEVEN_GATES, type GateState } from '../../../src/shared/types/api';

function seedSession() {
  useSessionStore.getState().setAuth({
    sessionToken: 'tok',
    principalId: 'pid',
    principalName: 'Marcus Kerrigan',
    sessionId: 'sess-1',
    correlationId: '4f8c2a11-d8e1-4412-8b22-99a7b0b4d8ab',
  });
  useSessionStore.getState().setConnectionStatus('open');
}

describe('AuditStripV2', () => {
  beforeEach(() => {
    useBriefStore.getState().reset();
    useSessionStore.getState().clearAuth();
    cleanup();
  });

  it('shows trace id (first 13 chars) and WS state', () => {
    seedSession();
    render(<AuditStripV2 />);
    expect(screen.getByText('4f8c2a11-d8e1')).toBeInTheDocument();
    // live-dot has the text "ws: open"
    expect(screen.getByText(/ws: open/)).toBeInTheDocument();
  });

  it('shows "no active spans" when brief store is empty', () => {
    seedSession();
    render(<AuditStripV2 />);
    expect(screen.getByText('no active spans')).toBeInTheDocument();
  });

  it('renders one pill per unique agent and escalates status', () => {
    seedSession();
    useBriefStore.getState().startTurn('t1');
    useBriefStore.getState().addToolCall({
      span_id: 's1',
      tool_name: 'get_quote',
      agent_id: 'market_specialist',
      started_at: '2026-04-30T06:14:30.000Z',
      status: 'running',
    });
    useBriefStore.getState().addToolCall({
      span_id: 's2',
      tool_name: 'get_technicals',
      agent_id: 'market_specialist',
      started_at: '2026-04-30T06:14:30.100Z',
      status: 'ok',
      latency_ms: 220,
    });
    useBriefStore.getState().addToolCall({
      span_id: 's3',
      tool_name: 'tavily_search',
      agent_id: 'sentiment_specialist',
      started_at: '2026-04-30T06:14:30.000Z',
      status: 'ok',
      latency_ms: 340,
    });
    render(<AuditStripV2 />);
    // One pill per agent, so we have 2 pills total
    expect(screen.getByText('market_specialist')).toBeInTheDocument();
    expect(screen.getByText('sentiment_specialist')).toBeInTheDocument();
  });

  it('shows HITL-hold indicator when gate ④ is in progress', () => {
    seedSession();
    const gates: GateState[] = SEVEN_GATES.map((name) => ({
      name,
      status: name === 'hitl' ? 'in_progress' : name === 'compliance' ? 'passed' : 'pending',
      started_at: name === 'hitl' ? new Date(Date.now() - 2000).toISOString() : undefined,
    }));
    render(<AuditStripV2 gates={gates} />);
    expect(screen.getByText(/HITL hold · gate ④/)).toBeInTheDocument();
  });
});

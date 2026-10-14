/**
 * Integration: feeding a realistic inbound WS event sequence through
 * `useStreamingTurn` updates both the brief store (existing behaviour) AND
 * the new traversal + traversalHistory stores.
 */

import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useStreamingTurn } from '../../src/shared/hooks/useStreamingTurn';
import { useBriefStore } from '../../src/shared/store/brief';
import { useTraversalStore } from '../../src/shared/store/traversal';
import { useTraversalHistoryStore } from '../../src/shared/store/traversalHistory';
import { useSessionStore } from '../../src/shared/store/session';
import type { InboundMessage } from '../../src/shared/types/agent';

describe('useStreamingTurn wires brief + traversal + history stores', () => {
  beforeEach(() => {
    useBriefStore.getState().reset();
    useTraversalStore.getState().reset();
    useTraversalHistoryStore.getState().clear();
    useSessionStore.setState({
      sessionToken: 'tok',
      principalId: 'sarah',
      principalName: 'Sarah Chen',
      persona: 'fsi_research',
      sessionId: 'sess',
      correlationId: 'corr-xyz',
      connectionStatus: 'idle',
    });
  });

  it('processes a full research turn — all three stores reflect the traversal', () => {
    const { result } = renderHook(() =>
      useStreamingTurn({ getTurnText: () => 'Deep dive on NVDA' }),
    );

    const events: InboundMessage[] = [
      { type: 'turn_started', turn_id: 't-1', agent_id: 'research_orchestrator' },
      {
        type: 'tool_call_start',
        turn_id: 't-1',
        tool: {
          span_id: 'sp-quote',
          tool_name: 'get_quote',
          agent_id: 'market_specialist',
          started_at: new Date().toISOString(),
          status: 'running',
        },
      },
      {
        type: 'tool_call_start',
        turn_id: 't-1',
        tool: {
          span_id: 'sp-edgar',
          tool_name: 'get_10k',
          agent_id: 'filings_specialist',
          started_at: new Date().toISOString(),
          status: 'running',
        },
      },
      {
        type: 'brief_delta',
        turn_id: 't-1',
        span_id: 'sp-quote',
        delta: 'NVDA at 163.50. ',
      },
      {
        type: 'tool_call_end',
        turn_id: 't-1',
        span_id: 'sp-quote',
        status: 'ok',
        latency_ms: 214,
      },
      {
        type: 'tool_call_end',
        turn_id: 't-1',
        span_id: 'sp-edgar',
        status: 'error',
        latency_ms: 900,
        error: {
          agent_id: 'filings_specialist',
          error_type: 'timeout',
          message: 'edgar slow',
          recoverable: true,
          occurred_at: new Date().toISOString(),
        },
      },
      {
        type: 'turn_complete',
        turn_id: 't-1',
        cost_tokens: 1234,
        cost_usd: 0.023,
        duration_ms: 1500,
      },
    ];

    act(() => {
      for (const ev of events) {
        result.current(ev);
      }
    });

    // Brief store still works.
    const brief = useBriefStore.getState();
    expect(brief.markdown).toBe('NVDA at 163.50. ');
    expect(brief.toolCalls).toHaveLength(2);
    expect(brief.isStreaming).toBe(false);
    expect(brief.costUsd).toBeCloseTo(0.023);

    // Traversal store reflects every hop.
    const trav = useTraversalStore.getState();
    expect(trav.nodes.research_orchestrator!.state).toBe('pulse');
    expect(trav.nodes['market-data']!.state).toBe('solid');
    expect(trav.nodes['market-data']!.latency_ms).toBe(214);
    expect(trav.nodes['sec-edgar']!.state).toBe('error');
    expect(trav.nodes['sec-edgar']!.error).toBe('edgar slow');
    expect(trav.edges['market_specialist|market-data']!.state).toBe('complete');
    expect(trav.edges['filings_specialist|sec-edgar']!.state).toBe('complete');
    // completeTurn cleared the activePersona
    expect(trav.activePersona).toBeNull();

    // History store got exactly one entry for this turn.
    const hist = useTraversalHistoryStore.getState();
    expect(hist.entries).toHaveLength(1);
    const entry = hist.entries[0]!;
    expect(entry.turnId).toBe('t-1');
    expect(entry.text).toBe('Deep dive on NVDA');
    expect(entry.toolCount).toBe(2);
    expect(entry.durationMs).toBe(1500);
    expect(entry.costUsd).toBeCloseTo(0.023);
  });

  it('gate events update the traversal store and end up on the history entry', () => {
    const { result } = renderHook(() => useStreamingTurn({}));

    useSessionStore.setState({ persona: 'fsi_advisor' });

    act(() => {
      result.current({ type: 'turn_started', turn_id: 't-gate', agent_id: 'advisor_orchestrator' });
      result.current({
        type: 'gate_started',
        turn_id: 't-gate',
        plan_id: 'p1',
        gate: 'compliance',
        status: 'in_progress',
      });
      result.current({
        type: 'gate_passed',
        turn_id: 't-gate',
        plan_id: 'p1',
        gate: 'compliance',
        status: 'passed',
      });
      result.current({
        type: 'turn_complete',
        turn_id: 't-gate',
        cost_tokens: 10,
        cost_usd: 0,
        duration_ms: 200,
      });
    });

    const trav = useTraversalStore.getState();
    expect(trav.nodes['gate:compliance']!.state).toBe('solid');

    const hist = useTraversalHistoryStore.getState();
    expect(hist.entries[0]!.gateTrace.map((g) => g.status)).toEqual([
      'in_progress',
      'passed',
    ]);
  });
});

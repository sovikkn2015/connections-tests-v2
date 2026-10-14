/**
 * HttpAgentTransport — backend contract wiring tests.
 *
 * These tests lock the contract between `openclaw.agentcore_server`'s
 * response envelope and the frontend event stream the stores consume. If
 * the backend drops or renames a field, these tests fail and point at the
 * exact gap.
 *
 * Scenarios covered:
 *   1. Research persona response (text + specialist_trace + gate_trace) →
 *      turn_started, 5× tool_call_start+end, brief_delta, turn_complete
 *      with canonical gate trace.
 *   2. Advisor persona with action_plan → includes hitl_prompt event.
 *   3. Liaison persona with queue_updates → emits queue_update events.
 *   4. Backend returns non-canonical gate names → filtered out, UI only
 *      sees canonical 7.
 *   5. HTTP 504 timeout → error event with tier "recoverable".
 *   6. Approval round-trip → posts to /agent/approve and replays gate_trace
 *      as gate_passed / gate_failed events with 400ms spacing.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { HttpAgentTransport } from '../../../src/shared/lib/httpAgentTransport';
import type { InboundMessage } from '../../../src/shared/types/agent';

function makeTransport() {
  return new HttpAgentTransport({
    apiUrl: 'https://api.example.com/v3',
    sessionToken: 'test-tok',
    persona: 'fsi_research',
    principalId: 'test-principal',
  });
}

function collect(t: HttpAgentTransport): InboundMessage[] {
  const out: InboundMessage[] = [];
  t.onMessage((m) => out.push(m));
  return out;
}

describe('HttpAgentTransport — backend wiring', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('emits tool_call pairs from specialist_trace + canonical gate_trace', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        text: '# NVDA brief\n\nText…',
        cost_tokens: 10378,
        cost_usd: 0,
        duration_ms: 22001,
        gate_trace: [
          { gate: 'compliance', status: 'passed', detail: 'ALLOW' },
        ],
        specialist_trace: [
          { agent_id: 'market_specialist', status: 'passed', detail: 'tokens=1200' },
          { agent_id: 'filings_specialist', status: 'passed', detail: 'tokens=1400' },
          { agent_id: 'sentiment_specialist', status: 'failed', detail: 'timeout' },
        ],
        correlation_id: 'turn-1',
        session_id: 'sess-1',
        persona: 'fsi_research',
      }),
    } as unknown as Response);

    await t.send({ type: 'turn', turn_id: 'turn-1', text: 'NVDA earnings' });

    expect(fetchSpy).toHaveBeenCalledWith(
      'https://api.example.com/v3/agent/invoke',
      expect.any(Object),
    );

    const types = out.map((m) => m.type);
    expect(types).toContain('turn_started');
    expect(types.filter((t) => t === 'tool_call_start').length).toBe(3);
    expect(types.filter((t) => t === 'tool_call_end').length).toBe(3);
    expect(types).toContain('brief_delta');
    expect(types).toContain('turn_complete');

    const complete = out.find((m) => m.type === 'turn_complete');
    expect(complete).toBeTruthy();
    if (complete && complete.type === 'turn_complete') {
      expect(complete.gate_trace).toEqual([
        expect.objectContaining({ gate: 'compliance', status: 'passed' }),
      ]);
      expect(complete.cost_tokens).toBe(10378);
      expect(complete.duration_ms).toBe(22001);
    }

    const endSpans = out.filter((m) => m.type === 'tool_call_end');
    expect(endSpans[2]?.type === 'tool_call_end' && endSpans[2].status).toBe('error');
  });

  it('emits hitl_prompt when action_plan is present', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        text: 'Drafted a trim plan.',
        duration_ms: 18000,
        gate_trace: [
          { gate: 'guardrails', status: 'passed' },
          { gate: 'mnpi_filter', status: 'passed' },
          { gate: 'compliance', status: 'passed' },
        ],
        action_plan: {
          plan_id: 'plan-9d3a71fc',
          plan_hash: 'a'.repeat(64),
          action_type: 'submit_order',
          summary: 'Trim NVDA 14.2% -> 9.5%',
          client_household: 'Vance-A',
          notional_usd: 300003,
          requires_dual_auth: false,
          gates: [],
        },
        correlation_id: 'turn-adv',
      }),
    } as unknown as Response);

    await t.send({ type: 'turn', turn_id: 'turn-adv', text: 'Trim NVDA' });

    const hitl = out.find((m) => m.type === 'hitl_prompt');
    expect(hitl).toBeTruthy();
    if (hitl && hitl.type === 'hitl_prompt') {
      expect(hitl.plan.plan_id).toBe('plan-9d3a71fc');
      expect(hitl.plan.action_type).toBe('submit_order');
      expect(hitl.plan.notional_usd).toBe(300003);
    }
  });

  it('emits queue_update events for each backend queue_updates entry', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        text: 'I will loop in your RM.',
        duration_ms: 5000,
        gate_trace: [],
        queue_updates: [
          {
            queue: 'alerts',
            op: 'add',
            item: {
              id: 'item-1',
              kind: 'alerts',
              title: 'Eleanor question — NVDA',
              subtitle: 'pre-earnings concern',
              timestamp: '2026-04-30T06:09:00Z',
              unread: true,
            },
          },
        ],
      }),
    } as unknown as Response);

    await t.send({ type: 'turn', turn_id: 't-liaison', text: 'question' });

    const queueEv = out.find((m) => m.type === 'queue_update');
    expect(queueEv).toBeTruthy();
    if (queueEv && queueEv.type === 'queue_update') {
      expect(queueEv.queue).toBe('alerts');
      expect(queueEv.op).toBe('add');
      expect(queueEv.item_id).toBe('item-1');
    }
  });

  it('filters non-canonical gate names from the turn_complete gate_trace', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        text: 'brief',
        duration_ms: 1000,
        gate_trace: [
          { gate: 'compliance', status: 'passed' },
          { gate: 'mcp_invoke', status: 'passed' },  // non-canonical — should drop
          { gate: 'hitl', status: 'in_progress' },
          { gate: 'random_skill', status: 'passed' },  // non-canonical — should drop
        ],
      }),
    } as unknown as Response);

    await t.send({ type: 'turn', turn_id: 't-gates', text: 'x' });

    const complete = out.find((m) => m.type === 'turn_complete');
    expect(complete).toBeTruthy();
    if (complete && complete.type === 'turn_complete') {
      const gates = complete.gate_trace ?? [];
      expect(gates.map((g) => g.gate)).toEqual(['compliance', 'hitl']);
    }
  });

  it('emits recoverable error on HTTP 504 timeout', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 504,
      json: async () => ({ status: 'error', error: { message: 'timeout' } }),
    } as unknown as Response);

    await t.send({ type: 'turn', turn_id: 't-timeout', text: 'big query' });

    const err = out.find((m) => m.type === 'error');
    expect(err).toBeTruthy();
    if (err && err.type === 'error') {
      expect(err.tier).toBe('recoverable');
    }
  });

  it('posts to /agent/approve and replays gate_passed events staggered at 400ms', async () => {
    const t = makeTransport();
    const out = collect(t);
    t.connect();

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'ok',
        plan_id: 'plan-123',
        gate_trace: [
          { gate: 'hitl', status: 'passed' },
          { gate: 'dual_auth', status: 'passed' },
          { gate: 'mulesoft', status: 'failed', detail: 'CloudHub not deployed' },
          { gate: 'audit', status: 'passed' },
        ],
      }),
    } as unknown as Response);

    await t.send({
      type: 'hitl_approval',
      plan_id: 'plan-123',
      plan_hash: 'h'.repeat(64),
      approved: true,
      approver_principal_id: 'marcus',
    });

    // Verify /agent/approve was hit
    expect(fetchSpy).toHaveBeenCalledWith(
      'https://api.example.com/v3/agent/approve',
      expect.any(Object),
    );

    // Advance timers by 4 * 400ms to let all staggered setTimeout fire
    await vi.advanceTimersByTimeAsync(2000);

    const gateEvents = out.filter(
      (m) => m.type === 'gate_passed' || m.type === 'gate_failed',
    );
    expect(gateEvents.length).toBe(4);
    // hitl passed → gate_passed
    expect(gateEvents[0]?.type).toBe('gate_passed');
    if (gateEvents[0]?.type === 'gate_passed') expect(gateEvents[0].gate).toBe('hitl');
    // mulesoft failed → gate_failed
    const mulesoftEv = gateEvents.find(
      (e) => (e.type === 'gate_passed' || e.type === 'gate_failed') && e.gate === 'mulesoft',
    );
    expect(mulesoftEv?.type).toBe('gate_failed');
  });
});


describe('HttpAgentTransport — long-invoke routing', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('routes advisor action_write turns to longInvokeUrl when configured', async () => {
    const t = new HttpAgentTransport({
      apiUrl: 'https://api.example.com/v3',
      sessionToken: 'tok',
      persona: 'fsi_advisor',
      longInvokeUrl: 'https://abcd.lambda-url.us-east-1.on.aws/',
    });
    t.connect();

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', text: 'plan drafted', duration_ms: 42000 }),
    } as unknown as Response);

    await t.send({
      type: 'turn',
      turn_id: 'adv-turn-1',
      text: 'Trim Eleanor NVDA from 14% to 9.5%',
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'https://abcd.lambda-url.us-east-1.on.aws',
      expect.any(Object),
    );
  });

  it('keeps non-action advisor turns on /agent/invoke', async () => {
    const t = new HttpAgentTransport({
      apiUrl: 'https://api.example.com/v3',
      sessionToken: 'tok',
      persona: 'fsi_advisor',
      longInvokeUrl: 'https://abcd.lambda-url.us-east-1.on.aws/',
    });
    t.connect();

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', text: 'analysis', duration_ms: 6000 }),
    } as unknown as Response);

    await t.send({
      type: 'turn',
      turn_id: 'adv-turn-2',
      text: 'What is Eleanor NVDA concentration?',
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'https://api.example.com/v3/agent/invoke',
      expect.any(Object),
    );
  });

  it('never routes research or liaison turns to longInvokeUrl', async () => {
    for (const persona of ['fsi_research', 'fsi_client_liaison'] as const) {
      const t = new HttpAgentTransport({
        apiUrl: 'https://api.example.com/v3',
        sessionToken: 'tok',
        persona,
        longInvokeUrl: 'https://abcd.lambda-url.us-east-1.on.aws/',
      });
      t.connect();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', text: 'ok', duration_ms: 5000 }),
      } as unknown as Response);
      await t.send({
        type: 'turn',
        turn_id: `${persona}-turn`,
        text: 'Please sell NVDA', // verb would trigger, but only for advisor
      });
      expect(fetchSpy).toHaveBeenCalledWith(
        'https://api.example.com/v3/agent/invoke',
        expect.any(Object),
      );
      fetchSpy.mockRestore();
    }
  });

  it('falls back to /agent/invoke when longInvokeUrl is null', async () => {
    const t = new HttpAgentTransport({
      apiUrl: 'https://api.example.com/v3',
      sessionToken: 'tok',
      persona: 'fsi_advisor',
      longInvokeUrl: null,
    });
    t.connect();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', text: 'ok', duration_ms: 5000 }),
    } as unknown as Response);
    await t.send({
      type: 'turn',
      turn_id: 'adv-fallback',
      text: 'Trim NVDA',
    });
    expect(fetchSpy).toHaveBeenCalledWith(
      'https://api.example.com/v3/agent/invoke',
      expect.any(Object),
    );
  });
});

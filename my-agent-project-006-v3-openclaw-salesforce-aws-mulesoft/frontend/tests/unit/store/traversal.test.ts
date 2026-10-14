/**
 * Unit tests for the live traversal store — drives the Architecture Map panel.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useTraversalStore } from '../../../src/shared/store/traversal';

function snapshot() {
  return useTraversalStore.getState();
}

describe('traversal store', () => {
  beforeEach(() => {
    useTraversalStore.getState().reset();
  });

  it('startTurn resets every node to dim and every edge to dim', () => {
    const store = useTraversalStore.getState();
    store.markAgentActive('research_orchestrator');
    expect(snapshot().nodes.research_orchestrator!.state).toBe('pulse');

    store.startTurn('t-1', 'fsi_research');
    const s = snapshot();
    expect(s.turnId).toBe('t-1');
    expect(s.activePersona).toBe('fsi_research');
    expect(Object.values(s.nodes).every((n) => n.state === 'dim')).toBe(true);
    expect(Object.values(s.edges).every((e) => e.state === 'dim')).toBe(true);
  });

  it('toolCallStart transitions the target skill node from dim to pulse and lights the parent edge', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-2', 'fsi_research');
    store.markAgentActive('filings_specialist');
    store.toolCallStart('filings_specialist', 'rag_retrieve', 'span-1');

    const s = snapshot();
    expect(s.nodes['skill:rag_retrieve']!.state).toBe('pulse');
    expect(s.nodes.filings_specialist!.state).toBe('pulse');
    // Edge filings_specialist -> skill:rag_retrieve should be active
    expect(s.edges['filings_specialist|skill:rag_retrieve']!.state).toBe('active');
  });

  it('toolCallEnd with status=ok settles the node to solid and the edge to complete', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-3', 'fsi_research');
    store.markAgentActive('market_specialist');
    store.toolCallStart('market_specialist', 'get_quote', 'span-q');
    store.toolCallEnd('span-q', 'ok', 142);

    const s = snapshot();
    expect(s.nodes['market-data']!.state).toBe('solid');
    expect(s.nodes['market-data']!.latency_ms).toBe(142);
    expect(s.edges['market_specialist|market-data']!.state).toBe('complete');
  });

  it('toolCallEnd with status=error transitions the node to error and stamps the error message', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-4', 'fsi_research');
    store.markAgentActive('sentiment_specialist');
    store.toolCallStart('sentiment_specialist', 'tavily_search', 'span-n');
    store.toolCallEnd('span-n', 'error', 90, 'tavily 503');

    const s = snapshot();
    expect(s.nodes['news-search']!.state).toBe('error');
    expect(s.nodes['news-search']!.error).toBe('tavily 503');
    expect(s.edges['sentiment_specialist|news-search']!.state).toBe('complete');
  });

  it('gateEvent drives virtual gate nodes and keeps action_specialist lit', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-5', 'fsi_advisor');
    store.markAgentActive('advisor_orchestrator');
    store.markAgentActive('action_specialist');

    store.gateEvent('compliance', 'in_progress');
    expect(snapshot().nodes['gate:compliance']!.state).toBe('pulse');
    expect(snapshot().nodes.action_specialist!.state).toBe('pulse');

    store.gateEvent('compliance', 'passed');
    expect(snapshot().nodes['gate:compliance']!.state).toBe('solid');

    store.gateEvent('hitl', 'failed');
    expect(snapshot().nodes['gate:hitl']!.state).toBe('error');
    expect(snapshot().nodes.action_specialist!.state).toBe('error');
  });

  it('gateEvent activates the sequential edge from the previous gate (serial proof)', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-5b', 'fsi_advisor');
    store.markAgentActive('action_specialist');

    // Gate 1 — edge action_specialist -> gate:guardrails should light
    store.gateEvent('guardrails', 'in_progress');
    expect(snapshot().edges['action_specialist|gate:guardrails']!.state).toBe('active');

    store.gateEvent('guardrails', 'passed');
    expect(snapshot().edges['action_specialist|gate:guardrails']!.state).toBe('complete');

    // Gate 3 — skipping gate 2 in-progress, but gate:mnpi_filter -> gate:compliance
    // should still light when compliance is reported
    store.gateEvent('compliance', 'in_progress');
    expect(snapshot().edges['gate:mnpi_filter|gate:compliance']!.state).toBe('active');
  });

  it('completeTurn preserves final node states but clears activePersona', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-6', 'fsi_research');
    store.markAgentActive('research_orchestrator');
    store.toolCallStart('market_specialist', 'get_quote', 'span-end');
    store.toolCallEnd('span-end', 'ok', 200);

    store.completeTurn();
    const s = snapshot();
    expect(s.activePersona).toBeNull();
    expect(s.nodes['market-data']!.state).toBe('solid');
    expect(s.nodes.research_orchestrator!.state).toBe('pulse');
  });

  it('double-start wipes residual state from the previous turn', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-a', 'fsi_research');
    store.markAgentActive('filings_specialist');
    store.toolCallStart('filings_specialist', 'rag_retrieve', 'span-a');
    store.toolCallEnd('span-a', 'ok', 120);

    // Now a new turn starts — everything must reset
    store.startTurn('t-b', 'fsi_advisor');
    const s = snapshot();
    expect(s.turnId).toBe('t-b');
    expect(s.activePersona).toBe('fsi_advisor');
    expect(s.nodes['skill:rag_retrieve']!.state).toBe('dim');
    expect(s.nodes.filings_specialist!.state).toBe('dim');
    expect(s.edges['filings_specialist|skill:rag_retrieve']!.state).toBe('dim');
  });

  it('unknown tool name does not crash and does not introduce phantom nodes', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const store = useTraversalStore.getState();
    store.startTurn('t-u', 'fsi_research');
    store.markAgentActive('market_specialist');

    expect(() =>
      store.toolCallStart('market_specialist', 'not_a_real_tool_7z', 'span-u'),
    ).not.toThrow();

    const s = snapshot();
    // Caller stays lit so the trail is visible.
    expect(s.nodes.market_specialist!.state).toBe('pulse');
    // No phantom node created.
    expect(s.nodes['skill:not_a_real_tool_7z']).toBeUndefined();

    // toolCallEnd for an unknown span is a no-op
    expect(() => store.toolCallEnd('span-u', 'ok', 50)).not.toThrow();
    warnSpy.mockRestore();
  });

  it('errored nodes stay errored even if a later pulse arrives', () => {
    const store = useTraversalStore.getState();
    store.startTurn('t-e', 'fsi_advisor');
    store.markAgentActive('action_specialist');
    store.toolCallStart('action_specialist', 'mulesoft_api', 'span-err');
    store.toolCallEnd('span-err', 'error', 300, 'HTTP 500');
    // Another call referencing the same skill pulses
    store.toolCallStart('action_specialist', 'mulesoft_api', 'span-retry');

    expect(snapshot().nodes['skill:mulesoft_api']!.state).toBe('error');
  });
});

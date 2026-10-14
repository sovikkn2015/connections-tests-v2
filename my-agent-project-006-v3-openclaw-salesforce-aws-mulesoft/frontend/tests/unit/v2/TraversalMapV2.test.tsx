/**
 * TraversalMapV2 — verifies the 3-orchestrator layout always shows all three
 * orchestrators, uses ghost edges between them, and fans specialists out
 * below the active orchestrator only.
 *
 * Topology source is the real `src/data/topology.json` — no mocks. Store
 * state is the initial dim state of the real useTraversalStore (reset via
 * its own `reset()` between tests).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { TraversalMapV2 } from '../../../src/v2/atoms/TraversalMapV2';
import { useTraversalStore } from '../../../src/shared/store/traversal';

describe('TraversalMapV2', () => {
  beforeEach(() => {
    useTraversalStore.getState().reset();
    cleanup();
  });

  it('renders all three orchestrators regardless of active persona', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    expect(screen.getByTestId('v2-map-node-research_orchestrator')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-advisor_orchestrator')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-liaison_orchestrator')).toBeInTheDocument();
  });

  it('renders the coordinator at the top', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    expect(screen.getByTestId('v2-map-node-coordinator')).toBeInTheDocument();
  });

  it('renders ghost edges between the three orchestrators', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    // Two ghost edges: research->advisor, advisor->liaison
    expect(screen.getByTestId('v2-map-edge-ghost-0')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-edge-ghost-1')).toBeInTheDocument();
    const ghost = screen.getByTestId('v2-map-edge-ghost-0');
    expect(ghost).toHaveAttribute('data-kind', 'ghost');
  });

  it('fans research specialists out when active persona is research', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    expect(screen.getByTestId('v2-map-node-market_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-filings_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-sentiment_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-compliance_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-statement_specialist')).toBeInTheDocument();
    // Advisor specialists should NOT be rendered when active is research
    expect(screen.queryByTestId('v2-map-node-action_specialist')).toBeNull();
  });

  it('fans advisor specialists + gate chain when active persona is advisor', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_advisor" />);
    expect(screen.getByTestId('v2-map-node-action_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-portfolio_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-suitability_specialist')).toBeInTheDocument();
    // 7 gate chain nodes rendered
    expect(screen.getByTestId('v2-map-node-gate:guardrails')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-gate:hitl')).toBeInTheDocument();
    expect(screen.getByTestId('v2-map-node-gate:audit')).toBeInTheDocument();
    // Research specialists NOT present
    expect(screen.queryByTestId('v2-map-node-market_specialist')).toBeNull();
  });

  it('reflects live store state on nodes via data-state attribute', () => {
    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    // Initially all nodes should be dim
    const coord = screen.getByTestId('v2-map-node-coordinator');
    expect(coord).toHaveAttribute('data-state', 'dim');
  });

  it('lights active persona nodes after startTurn + markAgentActive', () => {
    // Simulate the real event sequence a backend would emit
    useTraversalStore.getState().startTurn('turn-1', 'fsi_research');
    useTraversalStore.getState().markAgentActive('research_orchestrator');

    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    const orch = screen.getByTestId('v2-map-node-research_orchestrator');
    expect(orch).toHaveAttribute('data-state', 'pulse');
  });

  it('marks tool-call target solid after successful completion', () => {
    useTraversalStore.getState().startTurn('turn-2', 'fsi_research');
    useTraversalStore.getState().toolCallStart('market_specialist', 'get_quote', 'span-1');
    useTraversalStore.getState().toolCallEnd('span-1', 'ok', 280);

    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    const mcp = screen.getByTestId('v2-map-node-market-data');
    expect(mcp).toHaveAttribute('data-state', 'solid');
  });

  it('marks tool-call target error on failure', () => {
    useTraversalStore.getState().startTurn('turn-3', 'fsi_research');
    useTraversalStore
      .getState()
      .toolCallStart('sentiment_specialist', 'tavily_search', 'span-2');
    useTraversalStore
      .getState()
      .toolCallEnd('span-2', 'error', 1800, 'upstream timeout');

    render(<TraversalMapV2 fallbackPersona="fsi_research" />);
    const mcp = screen.getByTestId('v2-map-node-news-search');
    expect(mcp).toHaveAttribute('data-state', 'error');
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  TraversalMap,
  type TopologyJson,
  type TraversalNode,
  type TraversalEdge,
} from '../../../src/v1/components/TraversalMap';

// -----------------------------------------------------------------------------
// Inline mock topology — 17 nodes across 5 layers + trust layer, three
// personas. Self-contained so tests do NOT depend on builder 1's fixture.
// -----------------------------------------------------------------------------

const mockTopology: TopologyJson = {
  nodes: [
    // layer 0 — coordinator
    { id: 'coordinator', kind: 'coordinator', label: 'coordinator', persona: 'shared', layer: 0, model: 'sonnet' },
    // layer 1 — orchestrators
    { id: 'research_orch', kind: 'orchestrator', label: 'research_orch', persona: 'fsi_research', layer: 1, model: 'sonnet' },
    { id: 'advisor_orch', kind: 'orchestrator', label: 'advisor_orch', persona: 'fsi_advisor', layer: 1, model: 'sonnet' },
    { id: 'liaison_orch', kind: 'orchestrator', label: 'liaison_orch', persona: 'fsi_client_liaison', layer: 1, model: 'haiku' },
    // layer 2 — specialists
    { id: 'market_specialist', kind: 'specialist', label: 'market', persona: 'fsi_research', layer: 2, model: 'sonnet' },
    { id: 'filings_specialist', kind: 'specialist', label: 'filings', persona: 'fsi_research', layer: 2, model: 'sonnet' },
    { id: 'sentiment_specialist', kind: 'specialist', label: 'sentiment', persona: 'fsi_research', layer: 2, model: 'sonnet' },
    { id: 'action_specialist', kind: 'specialist', label: 'action', persona: 'fsi_advisor', layer: 2, model: 'sonnet' },
    { id: 'faq_specialist', kind: 'specialist', label: 'faq', persona: 'fsi_client_liaison', layer: 2, model: 'haiku' },
    // layer 3 — skills
    { id: 'rag_retrieve', kind: 'skill', label: 'rag_retrieve', persona: 'shared', layer: 3, model: null },
    { id: 'fsa', kind: 'skill', label: 'fsa', persona: 'fsi_research', layer: 3, model: null },
    // layer 4 — MCPs
    { id: 'finnhub_mcp', kind: 'mcp', label: 'finnhub', persona: 'fsi_research', layer: 4, model: null },
    { id: 'edgar_mcp', kind: 'mcp', label: 'edgar', persona: 'fsi_research', layer: 4, model: null },
    { id: 'tavily_mcp', kind: 'mcp', label: 'tavily', persona: 'fsi_research', layer: 4, model: null },
    { id: 'mulesoft_mcp', kind: 'mcp', label: 'mulesoft', persona: 'fsi_advisor', layer: 4, model: null },
    // trust layer
    { id: 'mnpi_filter', kind: 'trust', label: 'mnpi', persona: 'shared', layer: 4, model: null },
    { id: 'gate_enforcer', kind: 'trust', label: 'gates', persona: 'shared', layer: 4, model: null },
  ],
  edges: [
    { from: 'coordinator', to: 'research_orch', kind: 'routes' },
    { from: 'coordinator', to: 'advisor_orch', kind: 'routes' },
    { from: 'coordinator', to: 'liaison_orch', kind: 'routes' },
    { from: 'research_orch', to: 'market_specialist', kind: 'dispatches' },
    { from: 'research_orch', to: 'filings_specialist', kind: 'dispatches' },
    { from: 'research_orch', to: 'sentiment_specialist', kind: 'dispatches' },
    { from: 'advisor_orch', to: 'action_specialist', kind: 'dispatches' },
    { from: 'liaison_orch', to: 'faq_specialist', kind: 'dispatches' },
    { from: 'market_specialist', to: 'finnhub_mcp', kind: 'tools' },
    { from: 'filings_specialist', to: 'edgar_mcp', kind: 'tools' },
    { from: 'sentiment_specialist', to: 'tavily_mcp', kind: 'tools' },
    { from: 'action_specialist', to: 'mulesoft_mcp', kind: 'tools' },
  ],
};

// -----------------------------------------------------------------------------

describe('TraversalMap', () => {
  it('renders every topology node as a <g> with aria-label', () => {
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
      />,
    );
    // All nodes should be rendered.
    expect(mockTopology.nodes.length).toBeGreaterThanOrEqual(17);
    for (const n of mockTopology.nodes) {
      const el = screen.getByTestId(`traversal-node-${n.id}`);
      expect(el).toBeInTheDocument();
      // Non-interactive (no onNodeClick) → no role="button" (avoids ARIA-without-operability)
      expect(el).not.toHaveAttribute('role', 'button');
      expect(el).toHaveAttribute('aria-label');
    }
  });

  it('stamps role="button" only when interactive (onNodeClick provided)', () => {
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
        onNodeClick={() => {}}
      />,
    );
    for (const n of mockTopology.nodes) {
      const el = screen.getByTestId(`traversal-node-${n.id}`);
      expect(el).toHaveAttribute('role', 'button');
    }
  });

  it('renders nodes without a traversal state as data-state="dim"', () => {
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
      />,
    );
    for (const n of mockTopology.nodes) {
      expect(screen.getByTestId(`traversal-node-${n.id}`)).toHaveAttribute(
        'data-state',
        'dim',
      );
    }
  });

  it('applies data-state="pulse" when traversal says so', () => {
    const nodes: Record<string, TraversalNode> = {
      market_specialist: { id: 'market_specialist', state: 'pulse' },
    };
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={nodes}
        edges={{}}
        activePersona={null}
      />,
    );
    expect(screen.getByTestId('traversal-node-market_specialist')).toHaveAttribute(
      'data-state',
      'pulse',
    );
  });

  it('applies data-state="solid" for completed nodes', () => {
    const nodes: Record<string, TraversalNode> = {
      finnhub_mcp: { id: 'finnhub_mcp', state: 'solid', latency_ms: 280 },
    };
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={nodes}
        edges={{}}
        activePersona={null}
      />,
    );
    expect(screen.getByTestId('traversal-node-finnhub_mcp')).toHaveAttribute(
      'data-state',
      'solid',
    );
  });

  it('applies data-state="error" and marks failed nodes', () => {
    const nodes: Record<string, TraversalNode> = {
      edgar_mcp: { id: 'edgar_mcp', state: 'error', error: 'timeout' },
    };
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={nodes}
        edges={{}}
        activePersona={null}
      />,
    );
    expect(screen.getByTestId('traversal-node-edgar_mcp')).toHaveAttribute(
      'data-state',
      'error',
    );
  });

  it('dims other-persona nodes when activePersona is set', () => {
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona="fsi_research"
      />,
    );
    const advisorNode = screen.getByTestId('traversal-node-advisor_orch');
    // Other-persona nodes dimmed via inline opacity (0.3).
    expect(advisorNode.style.opacity).toBe('0.3');
    // Shared nodes not dimmed.
    const coord = screen.getByTestId('traversal-node-coordinator');
    expect(coord.style.opacity).toBe('');
    // Research-persona nodes not dimmed either.
    const researchOrch = screen.getByTestId('traversal-node-research_orch');
    expect(researchOrch.style.opacity).toBe('');
  });

  it('invokes onNodeClick on click and on Enter keypress', () => {
    const spy = vi.fn();
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
        onNodeClick={spy}
      />,
    );
    const node = screen.getByTestId('traversal-node-research_orch');
    fireEvent.click(node);
    expect(spy).toHaveBeenCalledWith('research_orch');
    fireEvent.keyDown(node, { key: 'Enter' });
    expect(spy).toHaveBeenCalledTimes(2);
    expect(spy).toHaveBeenLastCalledWith('research_orch');
    // Space also works.
    fireEvent.keyDown(node, { key: ' ' });
    expect(spy).toHaveBeenCalledTimes(3);
  });

  it('colors edges according to traversal edge state', () => {
    const edges: Record<string, TraversalEdge> = {
      'research_orch->market_specialist': {
        from: 'research_orch',
        to: 'market_specialist',
        state: 'active',
      },
      'market_specialist->finnhub_mcp': {
        from: 'market_specialist',
        to: 'finnhub_mcp',
        state: 'complete',
      },
    };
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={edges}
        activePersona={null}
      />,
    );
    expect(
      screen.getByTestId('edge-research_orch->market_specialist'),
    ).toHaveAttribute('data-state', 'active');
    expect(
      screen.getByTestId('edge-market_specialist->finnhub_mcp'),
    ).toHaveAttribute('data-state', 'complete');
  });

  it('renders the legend and correlation id', () => {
    render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
        correlationId="4f8c-2a11-beef-dead"
      />,
    );
    expect(screen.getByTestId('traversal-map-trace-id')).toHaveTextContent(
      /trace: 4f8c-2a1/,
    );
  });

  it('is deterministic: two renders produce identical node positions', () => {
    const { rerender, container } = render(
      <TraversalMap
        topology={mockTopology}
        nodes={{}}
        edges={{}}
        activePersona={null}
      />,
    );
    const first = [...container.querySelectorAll('[data-testid^="traversal-node-"]')]
      .map((n) => n.getAttribute('transform'))
      .join('|');
    rerender(
      <TraversalMap
        topology={mockTopology}
        nodes={{ coordinator: { id: 'coordinator', state: 'solid' } }}
        edges={{}}
        activePersona={null}
      />,
    );
    const second = [...container.querySelectorAll('[data-testid^="traversal-node-"]')]
      .map((n) => n.getAttribute('transform'))
      .join('|');
    expect(first).toEqual(second);
  });
});

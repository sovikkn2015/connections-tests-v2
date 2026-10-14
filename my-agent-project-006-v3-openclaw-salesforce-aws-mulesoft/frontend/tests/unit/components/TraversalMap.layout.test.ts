import { describe, it, expect } from 'vitest';
import {
  layoutTopology,
  DEFAULT_LAYOUT,
  type TopologyJson,
} from '../../../src/v1/components/TraversalMap';

// Pure layout tests — no React. Small topology that covers all five layers +
// a trust node, so we can assert ordering and non-overlap.
const topology: TopologyJson = {
  nodes: [
    { id: 'coordinator', kind: 'coordinator', label: 'coord', persona: 'shared', layer: 0, model: 'sonnet' },
    { id: 'research_orch', kind: 'orchestrator', label: 'research_orch', persona: 'fsi_research', layer: 1, model: 'sonnet' },
    { id: 'advisor_orch', kind: 'orchestrator', label: 'advisor_orch', persona: 'fsi_advisor', layer: 1, model: 'sonnet' },
    { id: 'liaison_orch', kind: 'orchestrator', label: 'liaison_orch', persona: 'fsi_client_liaison', layer: 1, model: 'haiku' },
    { id: 'market_spec', kind: 'specialist', label: 'market', persona: 'fsi_research', layer: 2, model: 'sonnet' },
    { id: 'filings_spec', kind: 'specialist', label: 'filings', persona: 'fsi_research', layer: 2, model: 'sonnet' },
    { id: 'action_spec', kind: 'specialist', label: 'action', persona: 'fsi_advisor', layer: 2, model: 'sonnet' },
    { id: 'faq_spec', kind: 'specialist', label: 'faq', persona: 'fsi_client_liaison', layer: 2, model: 'haiku' },
    { id: 'rag_skill', kind: 'skill', label: 'rag', persona: 'shared', layer: 3, model: null },
    { id: 'fsa_skill', kind: 'skill', label: 'fsa', persona: 'fsi_research', layer: 3, model: null },
    { id: 'finnhub_mcp', kind: 'mcp', label: 'finnhub', persona: 'fsi_research', layer: 4, model: null },
    { id: 'edgar_mcp', kind: 'mcp', label: 'edgar', persona: 'fsi_research', layer: 4, model: null },
    { id: 'tavily_mcp', kind: 'mcp', label: 'tavily', persona: 'fsi_research', layer: 4, model: null },
    { id: 'mulesoft_mcp', kind: 'mcp', label: 'mulesoft', persona: 'fsi_advisor', layer: 4, model: null },
    // trust layer
    { id: 'mnpi_filter', kind: 'trust', label: 'mnpi', persona: 'shared', layer: 4, model: null },
    { id: 'gate_enforcer', kind: 'trust', label: 'gates', persona: 'shared', layer: 4, model: null },
  ],
  edges: [],
};

describe('layoutTopology', () => {
  it('places layer 0 above layer 1, and so on downwards, with trust nodes at the bottom', () => {
    const pos = layoutTopology(topology);
    const coordY = pos.coordinator!.y;
    const orchY = pos.research_orch!.y;
    const specY = pos.market_spec!.y;
    const skillY = pos.rag_skill!.y;
    const mcpY = pos.finnhub_mcp!.y;
    const trustY = pos.mnpi_filter!.y;

    expect(coordY).toBeLessThan(orchY);
    expect(orchY).toBeLessThan(specY);
    expect(specY).toBeLessThan(skillY);
    expect(skillY).toBeLessThan(mcpY);
    // Trust row sits BELOW the MCPs (dedicated row at the bottom).
    expect(mcpY).toBeLessThan(trustY);
  });

  it('is deterministic: identical topology → identical positions', () => {
    const a = layoutTopology(topology);
    const b = layoutTopology(topology);
    expect(a).toEqual(b);
  });

  it('produces non-overlapping x coordinates within a single row for common widths', () => {
    // Default layout width = 1200. At layer 4 we have 4 MCPs — spread them out
    // so the smallest x-delta between adjacent MCPs is comfortably larger than
    // the node width (110px).
    const pos = layoutTopology(topology, { width: 1200 });
    const mcpXs = [
      pos.finnhub_mcp!.x,
      pos.edgar_mcp!.x,
      pos.mulesoft_mcp!.x,
      pos.tavily_mcp!.x,
    ].sort((a, b) => a - b);
    for (let i = 1; i < mcpXs.length; i++) {
      const delta = mcpXs[i]! - mcpXs[i - 1]!;
      // With 4 nodes across ~1104px usable width → step ≈ 368px. Very safe.
      expect(delta).toBeGreaterThan(110);
    }
  });

  it('respects the configured width (smaller viewports collapse spacing proportionally)', () => {
    const narrow = layoutTopology(topology, { width: 800 });
    const wide = layoutTopology(topology, { width: 1400 });
    // The leftmost MCP must stay within the narrower viewport.
    expect(narrow.finnhub_mcp!.x).toBeLessThanOrEqual(800 - DEFAULT_LAYOUT.paddingX + 1);
    // The rightmost MCP in the wider viewport should be further right than in
    // the narrow one.
    const narrowMax = Math.max(
      narrow.finnhub_mcp!.x,
      narrow.edgar_mcp!.x,
      narrow.mulesoft_mcp!.x,
      narrow.tavily_mcp!.x,
    );
    const wideMax = Math.max(
      wide.finnhub_mcp!.x,
      wide.edgar_mcp!.x,
      wide.mulesoft_mcp!.x,
      wide.tavily_mcp!.x,
    );
    expect(wideMax).toBeGreaterThan(narrowMax);
  });
});

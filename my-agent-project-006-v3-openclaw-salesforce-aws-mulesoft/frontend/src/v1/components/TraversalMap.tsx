/**
 * TraversalMap — always-visible live architecture graph.
 *
 * Hand-rolled SVG (no React Flow, no external deps). Every topology node renders
 * dim by default; the traversal record lights it up as events arrive.
 *
 * Props are pure data — this component owns NO state. Parents pass the topology,
 * the `nodes`/`edges` traversal record (from useTraversalStore), and the active
 * persona. A click handler is optional so the component is useful in read-only
 * contexts like tests and Storybook-style previews.
 *
 * Contract with builder 1:
 *   - topology.json shape: { nodes: TopologyNode[], edges: TopologyEdge[] }
 *   - traversal store: { nodes: Record<id, TraversalNode>, edges: Record<key, TraversalEdge>, activePersona }
 *
 * Layout is computed deterministically on every render from a pure function
 * (`layoutTopology`) so the map is stable across re-renders, snapshot tests,
 * and replay. Same input → same output.
 */

import { useMemo, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import type { Persona } from '../../shared/types/persona';
import type {
  NodeKind,
  NodePersona,
  NodeLayer,
  NodeModel,
  TopologyNode,
  EdgeKind,
  TopologyEdge,
  TopologyJson,
  TraversalNodeState,
  TraversalEdgeState,
  TraversalNode,
  TraversalEdge,
} from '../../shared/types/topology';

// Re-export topology types so existing callers that imported from this file
// continue to work (backward-compat during the reorg). Prefer importing
// directly from shared/types/topology in new code.
export type {
  NodeKind,
  NodePersona,
  NodeLayer,
  NodeModel,
  TopologyNode,
  EdgeKind,
  TopologyEdge,
  TopologyJson,
  TraversalNodeState,
  TraversalEdgeState,
  TraversalNode,
  TraversalEdge,
};

// ---------------------------------------------------------------------------
// Pure layout function — deterministic 5-row layered layout.
//
// Layer 0 → top (coordinator). Layers 1..3 are stacked below it. Layer 4 is
// the bottom row (MCPs). `trust` kind nodes get their own dedicated row below
// layer 4 so they always read as "cross-cutting controls", which is the
// narrative the design doc wants.
//
// For each row the nodes are sorted by [persona, id] for determinism and
// spread horizontally across `width` with an equal gap. This gives three
// persona "lanes" side by side when multiple personas share a layer, which
// matches the three-persona-graph requirement in the brief.
// ---------------------------------------------------------------------------

export interface LayoutOptions {
  width: number;
  height: number;
  paddingX: number;
  paddingTop: number;
  paddingBottom: number;
}

export interface NodePosition {
  x: number;
  y: number;
}

export const DEFAULT_LAYOUT: LayoutOptions = {
  width: 1200,
  height: 520,
  paddingX: 48,
  paddingTop: 40,
  paddingBottom: 40,
};

const PERSONA_ORDER: Record<NodePersona, number> = {
  fsi_research: 0,
  fsi_advisor: 1,
  fsi_client_liaison: 2,
  shared: 3,
};

/**
 * Pure, deterministic 5-row layered layout. Given the topology (and optional
 * options) returns a { [id]: {x,y} } map. Stable for snapshot tests.
 */
export function layoutTopology(
  topology: TopologyJson,
  options: Partial<LayoutOptions> = {},
): Record<string, NodePosition> {
  const opts: LayoutOptions = { ...DEFAULT_LAYOUT, ...options };
  const { width, height, paddingX, paddingTop, paddingBottom } = opts;

  // Bucket: layer 0..5 for non-trust; 'trust' kind → dedicated bottom row.
  const rows: Record<number, TopologyNode[]> = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [] };
  const trustRow: TopologyNode[] = [];
  for (const n of topology.nodes) {
    if (n.kind === 'trust') {
      trustRow.push(n);
    } else {
      rows[n.layer]?.push(n);
    }
  }

  // Total rows we actually render (6 layer rows + 1 trust row).
  const rowCount = 7;
  const usableHeight = Math.max(0, height - paddingTop - paddingBottom);
  const rowStep = rowCount > 1 ? usableHeight / (rowCount - 1) : 0;

  const positions: Record<string, NodePosition> = {};

  const placeRow = (nodes: TopologyNode[], rowIndex: number): void => {
    if (nodes.length === 0) return;
    // Stable sort by persona, then id → deterministic output.
    const sorted = [...nodes].sort((a, b) => {
      const dp = PERSONA_ORDER[a.persona] - PERSONA_ORDER[b.persona];
      if (dp !== 0) return dp;
      return a.id.localeCompare(b.id);
    });
    const y = paddingTop + rowIndex * rowStep;
    const usableWidth = Math.max(0, width - paddingX * 2);
    if (sorted.length === 1) {
      const only = sorted[0];
      if (only) positions[only.id] = { x: width / 2, y };
      return;
    }
    const step = usableWidth / (sorted.length - 1);
    sorted.forEach((n, i) => {
      positions[n.id] = { x: paddingX + step * i, y };
    });
  };

  placeRow(rows[0] ?? [], 0);
  placeRow(rows[1] ?? [], 1);
  placeRow(rows[2] ?? [], 2);
  placeRow(rows[3] ?? [], 3);
  placeRow(rows[4] ?? [], 4);
  placeRow(rows[5] ?? [], 5);
  placeRow(trustRow, 6);

  return positions;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface TraversalMapProps {
  topology: TopologyJson;
  nodes: Record<string, TraversalNode>;
  edges: Record<string, TraversalEdge>;
  activePersona: Persona | null;
  correlationId?: string | null;
  onNodeClick?: (id: string) => void;
  compact?: boolean;
}

const NODE_WIDTH = 110;
const NODE_HEIGHT = 34;

function edgeKey(from: string, to: string): string {
  return `${from}->${to}`;
}

function stateForNode(
  traversal: TraversalNode | undefined,
): TraversalNodeState {
  return traversal?.state ?? 'dim';
}

function stateForEdge(
  traversal: TraversalEdge | undefined,
): TraversalEdgeState {
  return traversal?.state ?? 'dim';
}

/**
 * Quadratic Bezier between two node centers. Curves downward for layered
 * top-to-bottom flow; SVG-safe d-attribute.
 */
function edgePath(from: NodePosition, to: NodePosition): string {
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2;
  // Add a slight downward sag so parallel edges don't overlap.
  const curveY = my + Math.min(30, Math.abs(to.y - from.y) * 0.2);
  return `M ${from.x} ${from.y + NODE_HEIGHT / 2} Q ${mx} ${curveY} ${to.x} ${to.y - NODE_HEIGHT / 2}`;
}

export function TraversalMap({
  topology,
  nodes,
  edges,
  activePersona,
  correlationId,
  onNodeClick,
  compact = false,
}: TraversalMapProps) {
  const positions = useMemo(
    () => layoutTopology(topology, compact ? { height: 340 } : undefined),
    [topology, compact],
  );

  const viewBox = `0 0 ${DEFAULT_LAYOUT.width} ${compact ? 340 : DEFAULT_LAYOUT.height}`;
  const containerStyle: CSSProperties = {
    width: '100%',
    minHeight: compact ? 220 : 340,
    maxHeight: compact ? 340 : 520,
  };

  const isPersonaDimmed = (nodePersona: NodePersona): boolean =>
    activePersona !== null && nodePersona !== 'shared' && nodePersona !== activePersona;

  const handleKey = (id: string) => (e: ReactKeyboardEvent<SVGGElement>): void => {
    if (!onNodeClick) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onNodeClick(id);
    }
  };

  return (
    <div className="v3-traversal-map" style={containerStyle} data-testid="traversal-map">
      <div className="v3-traversal-map__legend" aria-hidden="false">
        <span className="v3-traversal-map__legend-item" data-state="dim">⬤ dim</span>
        <span className="v3-traversal-map__legend-item" data-state="pulse">◐ pulse</span>
        <span className="v3-traversal-map__legend-item" data-state="solid">● solid</span>
        <span className="v3-traversal-map__legend-item" data-state="error">⨯ error</span>
        {correlationId && (
          <span
            className="v3-traversal-map__legend-item v3-traversal-map__trace-id"
            data-testid="traversal-map-trace-id"
          >
            trace: {correlationId.slice(0, 8)}
          </span>
        )}
      </div>
      <svg
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Live architecture traversal map"
        className="v3-traversal-map__svg"
        style={{ width: '100%', height: '100%' }}
      >
        {/* Edges first, so nodes sit on top */}
        <g className="v3-traversal-map__edges">
          {topology.edges.map((e) => {
            const from = positions[e.from];
            const to = positions[e.to];
            if (!from || !to) return null;
            const key = edgeKey(e.from, e.to);
            const state = stateForEdge(edges[key]);
            const fromNode = topology.nodes.find((n) => n.id === e.from);
            const toNode = topology.nodes.find((n) => n.id === e.to);
            const dimmed =
              (fromNode && isPersonaDimmed(fromNode.persona)) ||
              (toNode && isPersonaDimmed(toNode.persona));
            return (
              <path
                key={key}
                d={edgePath(from, to)}
                fill="none"
                className="v3-traversal-map__edge"
                data-state={state}
                data-kind={e.kind}
                data-testid={`edge-${key}`}
                style={dimmed ? { opacity: 0.3 } : undefined}
              />
            );
          })}
        </g>

        {/* Nodes */}
        <g className="v3-traversal-map__nodes">
          {topology.nodes.map((n) => {
            const pos = positions[n.id];
            if (!pos) return null;
            const state = stateForNode(nodes[n.id]);
            const dimmed = isPersonaDimmed(n.persona);
            const interactive = Boolean(onNodeClick);
            const x = pos.x - NODE_WIDTH / 2;
            const y = pos.y - NODE_HEIGHT / 2;

            return (
              <g
                key={n.id}
                transform={`translate(${x}, ${y})`}
                data-testid={`traversal-node-${n.id}`}
                data-state={state}
                data-kind={n.kind}
                data-persona={n.persona}
                role={interactive ? 'button' : undefined}
                tabIndex={interactive ? 0 : -1}
                aria-label={`${n.label} (${n.kind}, ${state})`}
                className="v3-traversal-map__node"
                onClick={interactive ? () => onNodeClick?.(n.id) : undefined}
                onKeyDown={interactive ? handleKey(n.id) : undefined}
                style={dimmed ? { opacity: 0.3 } : undefined}
              >
                <rect
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={6}
                  ry={6}
                  className="v3-traversal-map__node-rect"
                />
                <text
                  x={NODE_WIDTH / 2}
                  y={NODE_HEIGHT / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="v3-traversal-map__node-label"
                >
                  {n.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

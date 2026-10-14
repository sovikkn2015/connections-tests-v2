/**
 * V4 Architecture Map — plain-English, three zoom levels.
 *
 * Why this exists in its current shape: earlier V4 maps failed the "can
 * anyone but an engineer read this?" test. They showed 43 internal
 * codenames (`filings_specialist`, `mcp:sec-edgar`, `skill:rag_retrieve`)
 * and forced a business viewer to parse engineer jargon. This rewrite
 * adds three zoom levels so each audience sees the right register:
 *
 *   Simple (default) — ~9 nodes, plain English. For demos, exec reviews,
 *                      compliance officers. Shows the story: who works
 *                      the query and what they use.
 *   Detailed         — ~20 nodes. Adds the other personas' orchestrators
 *                      (shared trust spine) + the data sources + the
 *                      write-path gate chain for advisor. Still plain
 *                      English, more depth.
 *   Developer        — full 43-node topology with engineering ids. For
 *                      audit, debugging, the people who ship it.
 *
 * A caption strip below the map explains the persona's workflow in a
 * single sentence. The graph reinforces the sentence — it doesn't
 * replace it.
 *
 * Industry pattern: zoom levels are standard in agent-canvas UIs
 * (content rephrased for compliance with licensing restrictions;
 * sources: https://docs.langchain.com/oss/python/langgraph/studio,
 * https://reactflow.dev, n8n workflow visualiser).
 *
 * Edge + node state convention: activity signalled via node pulse ring
 * + colour fill. All edges share the same stroke-width (~1px);
 * colour + dashflow carry active state. This prevents the "thick-line
 * scar" pattern where a single lit edge dominates because it's thicker
 * than every dim edge.
 */

import { useCallback, useMemo, useState } from 'react';
import topologyJson from '../../shared/data/topology.json';
import {
  useTraversalStore,
  type TraversalNodeState,
} from '../../shared/store/traversal';
import { useSessionStore } from '../../shared/store/session';
import type { Persona } from '../../shared/types/persona';
import {
  captionFor,
  idsAtLevel,
  kindSimpleFor,
  labelFor,
  type MapLevel,
} from './mapLabels';

// ---------------------------------------------------------------------------
// Topology types
// ---------------------------------------------------------------------------

interface TopologyNode {
  id: string;
  kind: string;
  label: string;
  persona: string;
  model: string | null;
  detail?: string;
  layer: number;
}
interface TopologyEdge {
  from: string;
  to: string;
  kind: string;
}
interface TopologyShape {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

const TOPOLOGY = topologyJson as TopologyShape;

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const VIEW_W = 1240;
const ROW_Y: Record<number, number> = {
  0: 6,
  1: 58,
  2: 122,
  3: 186,
  4: 250,
  5: 320,
};
const FULL_VIEW_H = 360;
const NODE_H_CHIP = 22;

const NODE_W_BY_KIND_SIMPLE: Record<string, number> = {
  agent: 132,
  data: 118,
  gate: 122,
  root: 130,
};

interface LaidOutNode extends TopologyNode {
  x: number; // center x
  y: number;
  width: number;
  displayLabel: string;
  kindSimple: 'agent' | 'data' | 'gate' | 'root';
}

function layoutFiltered(
  level: MapLevel,
  persona: Persona,
  showGates: boolean,
): {
  nodes: LaidOutNode[];
  edges: TopologyEdge[];
  byId: Map<string, LaidOutNode>;
  viewH: number;
} {
  const visible = idsAtLevel(level, persona);
  const filteredNodes = TOPOLOGY.nodes.filter((n) => {
    if (n.kind === 'gate' && !showGates && level !== 'developer') return false;
    if (visible === null) return true; // developer mode
    return visible.has(n.id);
  });

  // Group into layer bands. In simple mode we compress to 3 rows for
  // readability; in detailed/developer we use the full layer schema.
  const nodesByLayer = new Map<number, TopologyNode[]>();
  for (const n of filteredNodes) {
    let layer = n.layer;
    if (level === 'simple') {
      // Simple mode: coordinator=0, agents+orchestrators=1, data/gates=2
      const ks = kindSimpleFor(n.id, n.kind);
      layer = ks === 'root' ? 0 : ks === 'agent' ? 1 : 2;
    }
    const bucket = nodesByLayer.get(layer) ?? [];
    bucket.push(n);
    nodesByLayer.set(layer, bucket);
  }

  // Deterministic within-row ordering: orchestrators before specialists
  // before trust; then alphabetical by id.
  for (const bucket of nodesByLayer.values()) {
    bucket.sort((a, b) => {
      const aPr =
        a.kind === 'orchestrator' ? 0 : a.kind === 'coordinator' ? -1 : a.kind === 'trust' ? 2 : 1;
      const bPr =
        b.kind === 'orchestrator' ? 0 : b.kind === 'coordinator' ? -1 : b.kind === 'trust' ? 2 : 1;
      if (aPr !== bPr) return aPr - bPr;
      return a.id.localeCompare(b.id);
    });
  }

  const out: LaidOutNode[] = [];
  const byId = new Map<string, LaidOutNode>();
  const layerEntries = Array.from(nodesByLayer.entries()).sort((a, b) => a[0] - b[0]);
  const yByLayer: Record<number, number> =
    level === 'simple' ? { 0: 6, 1: 74, 2: 162 } : ROW_Y;

  for (const [layer, bucket] of layerEntries) {
    const count = bucket.length;
    // Width depends on whether we're in simple mode (bigger chips) or
    // detailed/developer (compact chips).
    const baseWidth = (n: TopologyNode): number => {
      if (level === 'developer') {
        return n.kind === 'coordinator' ? 118 : n.kind === 'orchestrator' ? 112 : 100;
      }
      const ks = kindSimpleFor(n.id, n.kind);
      return NODE_W_BY_KIND_SIMPLE[ks] ?? 120;
    };
    const chipWidths = bucket.map(baseWidth);
    const gap = Math.max(12, (VIEW_W - chipWidths.reduce((a, b) => a + b, 0)) / (count + 1));
    let cursor = gap;
    bucket.forEach((n, i) => {
      const w = chipWidths[i]!;
      const laid: LaidOutNode = {
        ...n,
        x: cursor + w / 2,
        y: yByLayer[layer] ?? ROW_Y[layer] ?? 0,
        width: w,
        displayLabel: labelFor(n.id, level),
        kindSimple: kindSimpleFor(n.id, n.kind),
      };
      out.push(laid);
      byId.set(n.id, laid);
      cursor += w + gap;
    });
  }

  const viewH =
    level === 'simple'
      ? 240
      : showGates
        ? FULL_VIEW_H
        : (ROW_Y[4] ?? 250) + 40;

  // Edge filter: only keep edges where both endpoints are visible AND the
  // kind is meaningful at this level (simple hides sequences/tools/calls).
  const edges = TOPOLOGY.edges.filter((e) => {
    if (!byId.has(e.from) || !byId.has(e.to)) return false;
    if (level === 'simple') {
      return e.kind === 'routes' || e.kind === 'dispatches';
    }
    return true;
  });

  return { nodes: out, edges, byId, viewH };
}

// ---------------------------------------------------------------------------
// State resolution
// ---------------------------------------------------------------------------

function nodeState(
  id: string,
  storeNodes: Record<string, { state: TraversalNodeState }>,
): TraversalNodeState {
  return storeNodes[id]?.state ?? 'dim';
}

function opacityFor(node: TopologyNode, activePersona: Persona, level: MapLevel): number {
  if (level === 'simple') return 1; // simple view has no cross-persona noise
  if (node.persona === 'shared') return 1;
  if (node.persona === activePersona) return 1;
  return 0.4;
}

function edgeState(
  edge: TopologyEdge,
  storeNodes: Record<string, { state: TraversalNodeState }>,
): 'dim' | 'active' | 'complete' | 'error' {
  const to = storeNodes[edge.to];
  if (!to) return 'dim';
  if (to.state === 'error') return 'error';
  if (to.state === 'solid') return 'complete';
  if (to.state === 'pulse') return 'active';
  return 'dim';
}

function bezier(from: LaidOutNode, to: LaidOutNode): string {
  const fx = from.x;
  const fy = from.y + NODE_H_CHIP;
  const tx = to.x;
  const ty = to.y;
  if (Math.abs(fy - ty) < 6) {
    return `M${fx},${fy} L${tx},${ty}`;
  }
  const my = (fy + ty) / 2;
  return `M${fx},${fy} C${fx},${my} ${tx},${my} ${tx},${ty}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface TraversalMapV4Props {
  persona: Persona;
  langfuseBaseUrl?: string;
  showGates?: boolean;
  compact?: boolean;
  /** Initial zoom level. Default 'simple' so business viewers open into
   * the right register. User can toggle up to developer. */
  defaultLevel?: MapLevel;
}

const LEVEL_LABELS: Record<MapLevel, string> = {
  simple: 'Simple',
  detailed: 'Detailed',
  developer: 'Developer',
};

export function TraversalMapV4({
  persona,
  langfuseBaseUrl,
  showGates,
  compact = false,
  defaultLevel = 'simple',
}: TraversalMapV4Props) {
  const [level, setLevel] = useState<MapLevel>(defaultLevel);
  const storeNodes = useTraversalStore((s) => s.nodes);
  const activePersona = useTraversalStore((s) => s.activePersona);
  const turnId = useTraversalStore((s) => s.turnId);
  const correlationId = useSessionStore((s) => s.correlationId);

  const effectivePersona = activePersona ?? persona;
  const effectiveShowGates = showGates ?? effectivePersona === 'fsi_advisor';

  const { nodes, edges, byId, viewH } = useMemo(
    () => layoutFiltered(level, effectivePersona, effectiveShowGates),
    [level, effectivePersona, effectiveShowGates],
  );

  const openSpan = useCallback(
    (spanId: string) => {
      if (!langfuseBaseUrl || !correlationId) return;
      const base = langfuseBaseUrl.replace(/\/$/, '');
      const url = `${base}/trace/${encodeURIComponent(correlationId)}?span=${encodeURIComponent(spanId)}`;
      try {
        window.open(url, '_blank', 'noopener,noreferrer');
      } catch {
        /* ignore */
      }
    },
    [langfuseBaseUrl, correlationId],
  );

  const activeCount = nodes.filter((n) => nodeState(n.id, storeNodes) !== 'dim').length;
  const subtitle =
    activeCount > 0
      ? `${activeCount} working · ${nodes.length} nodes`
      : `${nodes.length} nodes · ready`;

  const canvasHeight = compact ? 180 : viewH + 12;

  const caption = captionFor(effectivePersona);

  return (
    <div
      className="traversal-map"
      data-testid="traversal-map-v4"
      data-persona={effectivePersona}
      data-level={level}
    >
      <div className="tm-header">
        <div className="tm-header__title">
          <span>Live workflow</span>
          <span
            className="w360-mono"
            style={{
              fontSize: 10,
              color: 'var(--v4-forensic-text-4)',
              textTransform: 'none',
              letterSpacing: 0,
            }}
          >
            {subtitle}
            {turnId ? ` · turn ${turnId.slice(0, 8)}` : ''}
          </span>
        </div>
        <div className="tm-header__controls" role="tablist" aria-label="Map detail level">
          {(['simple', 'detailed', 'developer'] as const).map((lv) => (
            <button
              key={lv}
              type="button"
              role="tab"
              aria-selected={level === lv}
              className="tm-level-btn"
              data-active={level === lv || undefined}
              onClick={() => setLevel(lv)}
              data-testid={`v4-map-level-${lv}`}
            >
              {LEVEL_LABELS[lv]}
            </button>
          ))}
        </div>
      </div>
      <div className="tm-canvas" style={{ height: canvasHeight }}>
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${VIEW_W} ${viewH}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Live workflow map"
        >
          <g data-testid="v4-map-edges">
            {edges.map((e, i) => {
              const from = byId.get(e.from);
              const to = byId.get(e.to);
              if (!from || !to) return null;
              const state = edgeState(e, storeNodes);
              const cls = `tm-edge tm-edge--${state}`;
              return (
                <path
                  key={`${e.from}-${e.to}-${i}`}
                  className={cls}
                  data-kind={e.kind}
                  d={bezier(from, to)}
                />
              );
            })}
          </g>
          {nodes.map((n) => {
            const state = nodeState(n.id, storeNodes);
            const op = opacityFor(n, effectivePersona, level);
            const x = n.x - n.width / 2;
            const isClickable = Boolean(langfuseBaseUrl && correlationId);
            const kindDataAttr = level === 'developer' ? n.kind : n.kindSimple;
            return (
              <g
                key={n.id}
                className="tm-node-g"
                data-kind={kindDataAttr}
                data-kind-simple={n.kindSimple}
                data-status={state}
                style={{ opacity: op, cursor: isClickable ? 'pointer' : 'default' }}
                onClick={() => openSpan(n.id)}
                data-testid={`v4-map-node-${n.id}`}
                role={isClickable ? 'button' : 'presentation'}
                aria-label={`${n.displayLabel} (${state})`}
              >
                {state === 'pulse' && (
                  <rect
                    className="tm-node__ring"
                    x={x - 3}
                    y={n.y - 3}
                    width={n.width + 6}
                    height={NODE_H_CHIP + 6}
                    rx={6}
                    ry={6}
                  />
                )}
                <rect
                  className="tm-node__bg"
                  x={x}
                  y={n.y}
                  width={n.width}
                  height={NODE_H_CHIP}
                  rx={4}
                  ry={4}
                />
                <text
                  x={n.x}
                  y={n.y + NODE_H_CHIP / 2 + 4}
                  textAnchor="middle"
                  className="tm-node__chip-text"
                >
                  {n.displayLabel.length > 28
                    ? n.displayLabel.slice(0, 26) + '…'
                    : n.displayLabel}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="tm-caption" data-testid="v4-map-caption">
        {caption}
      </div>
    </div>
  );
}

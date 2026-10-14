/**
 * TraversalMapV2 — 3-orchestrator architecture map with ghost spine edges.
 *
 * WHY THIS EXISTS
 * ---------------
 * The v1 TraversalMap renders all topology nodes at their layer, across all
 * personas simultaneously. It's data-accurate but hard to read — the "trust
 * spine across three personas" idea doesn't land.
 *
 * v2 uses a fixed 4-row layout:
 *    row 0: Coordinator (center)
 *    row 1: Three orchestrators (research | advisor | liaison)
 *    row 2: Specialists — fan out below the ACTIVE orchestrator
 *    row 3: Skills + MCPs — linked to their specialist
 *
 * Ghost dashed edges between the three orchestrators show "they share the
 * same graph" — not a data-flow, just a spine indicator.
 *
 * WIRING (all real, no mocks)
 * ---------------------------
 * - Topology source: `frontend/src/data/topology.json` (37 nodes, 54 edges)
 * - Live state: `useTraversalStore` (populated by WebSocket tool_call_* + gate events)
 * - Active persona: from the store (set by turn_started via persona in session)
 * - Correlation id: useSessionStore (for the Langfuse deep link)
 *
 * EVERY NARRATIVE uses the same map — the difference is which orchestrator +
 * specialist set lights up. See v3-frontend-v2-narrative-coverage.md for the
 * per-narrative light trace.
 */

import { useCallback, useMemo, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import type { Persona } from '../../shared/types/persona';
import topologyJson from '../../shared/data/topology.json';
import {
  useTraversalStore,
  type TraversalNode,
  type TraversalEdge,
  type TraversalNodeState,
} from '../../shared/store/traversal';
import { useSessionStore } from '../../shared/store/session';

// --------------------------------------------------------------------------
// Layout constants — pixel units, fixed viewport (scales responsively via
// viewBox). Keep in sync with v2-map.css.
// --------------------------------------------------------------------------

const VIEWBOX_W = 1240;
const NODE_W = 100;
const NODE_H_LABEL = 34; // bordered rect
const ROW_Y = {
  coord: 8,
  orch: 70,
  spec: 140,
  mcp_skill: 208,
  gate: 280,
};

// Orchestrator x-positions — evenly spaced across viewport.
const ORCH_X: Record<Persona, number> = {
  fsi_research: 100,
  fsi_advisor: 570,
  fsi_client_liaison: 1040,
};

const PERSONA_TAG: Record<Persona, string> = {
  fsi_research: 'research',
  fsi_advisor: 'advisor',
  fsi_client_liaison: 'client',
};

const ORCH_NODE_ID: Record<Persona, string> = {
  fsi_research: 'research_orchestrator',
  fsi_advisor: 'advisor_orchestrator',
  fsi_client_liaison: 'liaison_orchestrator',
};

const ORCH_LABEL: Record<Persona, string> = {
  fsi_research: 'research_orch',
  fsi_advisor: 'advisor_orch',
  fsi_client_liaison: 'liaison_orch',
};

// --------------------------------------------------------------------------
// Topology + derived lookups
// --------------------------------------------------------------------------

interface TopologyNodeRaw {
  id: string;
  kind: string;
  label: string;
  persona: string;
  model: string | null;
  detail?: string;
  layer: number;
}
interface TopologyEdgeRaw {
  from: string;
  to: string;
  kind: string;
}
interface TopologyJsonLike {
  nodes: TopologyNodeRaw[];
  edges: TopologyEdgeRaw[];
}

const TOPOLOGY: TopologyJsonLike = topologyJson;

/** childId -> parent dispatches edge (orchestrator → specialist). */
const SPEC_TO_ORCH: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const e of TOPOLOGY.edges) {
    if (e.kind === 'dispatches') out[e.to] = e.from;
  }
  return out;
})();

/** specialistId -> [skill ids] (calls) and [mcp ids] (tools). */
const SPEC_TO_SKILLS: Record<string, string[]> = (() => {
  const out: Record<string, string[]> = {};
  for (const e of TOPOLOGY.edges) {
    if (e.kind !== 'calls') continue;
    (out[e.from] ??= []).push(e.to);
  }
  return out;
})();

const SPEC_TO_MCPS: Record<string, string[]> = (() => {
  const out: Record<string, string[]> = {};
  for (const e of TOPOLOGY.edges) {
    if (e.kind !== 'tools') continue;
    (out[e.from] ??= []).push(e.to);
  }
  return out;
})();

function personaOf(_persona: string | undefined): Persona | 'shared' {
  if (_persona === 'fsi_research' || _persona === 'fsi_advisor' || _persona === 'fsi_client_liaison') {
    return _persona;
  }
  return 'shared';
}
// personaOf is kept for future layout variants; suppress unused-var warning.
void personaOf;

/** All specialist nodes belonging to a given persona orchestrator. Deterministic order. */
function specialistsFor(persona: Persona): TopologyNodeRaw[] {
  const orchId = ORCH_NODE_ID[persona];
  return TOPOLOGY.nodes
    .filter((n) => n.kind === 'specialist' && SPEC_TO_ORCH[n.id] === orchId)
    .sort((a, b) => a.id.localeCompare(b.id));
}

/** Gate nodes (sorted in canonical 1→7 order). */
const GATE_ORDER = [
  'gate:guardrails',
  'gate:mnpi_filter',
  'gate:compliance',
  'gate:hitl',
  'gate:dual_auth',
  'gate:mulesoft',
  'gate:audit',
] as const;

function gateNodes(): TopologyNodeRaw[] {
  const byId = new Map(TOPOLOGY.nodes.map((n) => [n.id, n]));
  return GATE_ORDER.map((id) => byId.get(id)).filter(
    (x): x is TopologyNodeRaw => x !== undefined,
  );
}

// --------------------------------------------------------------------------
// Layout (pure — takes persona, returns { nodes: {id->{x,y,kind,label,visible}}, edges: […] })
// --------------------------------------------------------------------------

interface LaidOutNode {
  id: string;
  x: number;
  y: number;
  kind: string;
  chip: string;
  label: string;
  personaTag: string;
  visible: boolean;
}

interface LaidOutEdge {
  id: string;
  from: LaidOutNode;
  to: LaidOutNode;
  kind: 'routes' | 'dispatches' | 'calls' | 'tools' | 'sequences' | 'ghost';
}

function layout(active: Persona, showGates: boolean): {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
} {
  const laidOutNodes: LaidOutNode[] = [];
  const byId = new Map<string, LaidOutNode>();

  // ---- row 0: Coordinator (center)
  const coord: LaidOutNode = {
    id: 'coordinator',
    x: VIEWBOX_W / 2 - NODE_W / 2,
    y: ROW_Y.coord,
    kind: 'coordinator',
    chip: 'coordinator',
    label: 'COORDINATOR',
    personaTag: 'shared',
    visible: true,
  };
  laidOutNodes.push(coord);
  byId.set('coordinator', coord);

  // ---- row 1: Three orchestrators (always all 3, even the inactive ones)
  (Object.keys(ORCH_NODE_ID) as Persona[]).forEach((persona) => {
    const id = ORCH_NODE_ID[persona];
    const node: LaidOutNode = {
      id,
      x: ORCH_X[persona],
      y: ROW_Y.orch,
      kind: 'orchestrator',
      chip: ORCH_LABEL[persona],
      label: 'ORCHESTRATOR',
      personaTag: PERSONA_TAG[persona],
      visible: true,
    };
    laidOutNodes.push(node);
    byId.set(id, node);
  });

  // ---- row 2: Specialists — only the active persona's fan out
  const specs = specialistsFor(active);
  const specBaseX = ORCH_X[active] - (specs.length - 1) * (NODE_W + 8) / 2;
  specs.forEach((s, i) => {
    const node: LaidOutNode = {
      id: s.id,
      x: specBaseX + i * (NODE_W + 8),
      y: ROW_Y.spec,
      kind: 'specialist',
      chip: s.label,
      label: 'specialist',
      personaTag: PERSONA_TAG[active],
      visible: true,
    };
    laidOutNodes.push(node);
    byId.set(s.id, node);
  });

  // ---- row 3: MCPs — one per specialist by dispatch order. If a specialist
  //    has multiple MCPs we stack them; most specialists have 1-2.
  //    Skills are shown interleaved with MCPs (skill kind = in-process,
  //    mcp = external) — both render at the same row.
  const row3Items: Array<{ id: string; specIdx: number; rank: number; kind: 'skill' | 'mcp' }> = [];
  specs.forEach((s, idx) => {
    const mcps = (SPEC_TO_MCPS[s.id] ?? []).filter((mid) => {
      const n = TOPOLOGY.nodes.find((nn) => nn.id === mid);
      return n && n.kind === 'mcp';
    });
    const skills = (SPEC_TO_SKILLS[s.id] ?? []).filter((sid) => {
      const n = TOPOLOGY.nodes.find((nn) => nn.id === sid);
      return n && n.kind === 'skill';
    });
    // Put MCPs first (bigger visual anchor) then skills; cap at 2 per spec so
    // the row doesn't overflow visually.
    const picks: Array<{ id: string; kind: 'skill' | 'mcp' }> = [];
    mcps.slice(0, 1).forEach((id) => picks.push({ id, kind: 'mcp' }));
    skills.slice(0, 1).forEach((id) => picks.push({ id, kind: 'skill' }));
    picks.forEach((p, rank) => row3Items.push({ ...p, specIdx: idx, rank }));
  });

  // Place each row3 item directly below its specialist; stacks offset by NODE_H_LABEL+6 vertically.
  row3Items.forEach((item) => {
    if (byId.has(item.id)) return; // already placed (shared MCP)
    const spec = byId.get(specs[item.specIdx]!.id)!;
    const y = ROW_Y.mcp_skill + item.rank * (NODE_H_LABEL + 8);
    const raw = TOPOLOGY.nodes.find((n) => n.id === item.id)!;
    const node: LaidOutNode = {
      id: item.id,
      x: spec.x,
      y,
      kind: item.kind,
      chip: raw.label.replace(/^skill:/, '').toLowerCase(),
      label: item.kind === 'skill' ? 'skill' : 'MCP',
      personaTag: PERSONA_TAG[active],
      visible: true,
    };
    laidOutNodes.push(node);
    byId.set(item.id, node);
  });

  // ---- row 4: Gate chain (advisor persona only, or when showGates=true)
  if (showGates || active === 'fsi_advisor') {
    const gates = gateNodes();
    const gateBaseX = (VIEWBOX_W - gates.length * NODE_W - (gates.length - 1) * 8) / 2;
    gates.forEach((g, i) => {
      const node: LaidOutNode = {
        id: g.id,
        x: gateBaseX + i * (NODE_W + 8),
        y: ROW_Y.gate,
        kind: 'gate',
        chip: g.label.replace(/^[①②③④⑤⑥⑦]\s*/, '').toLowerCase(),
        label: `gate ${i + 1}`,
        personaTag: 'advisor',
        visible: true,
      };
      laidOutNodes.push(node);
      byId.set(g.id, node);
    });
  }

  // --------------------------------------------------------------------
  // Edges
  // --------------------------------------------------------------------
  const edges: LaidOutEdge[] = [];

  // Coord → each orchestrator (real topology edge)
  (Object.keys(ORCH_NODE_ID) as Persona[]).forEach((p) => {
    const target = byId.get(ORCH_NODE_ID[p]);
    if (target) {
      edges.push({
        id: `coord-${p}`,
        from: coord,
        to: target,
        kind: 'routes',
      });
    }
  });

  // Ghost spine edges between orchestrators — UI construct, not in topology.json.
  // These show "all three share the same coordinator graph" without implying a data flow.
  const orchIds = (Object.keys(ORCH_NODE_ID) as Persona[]).map((p) => ORCH_NODE_ID[p]);
  for (let i = 0; i < orchIds.length - 1; i++) {
    const from = byId.get(orchIds[i]!);
    const to = byId.get(orchIds[i + 1]!);
    if (from && to) {
      edges.push({
        id: `ghost-${i}`,
        from,
        to,
        kind: 'ghost',
      });
    }
  }

  // Active orch → specialists (dispatches)
  specs.forEach((s) => {
    const from = byId.get(ORCH_NODE_ID[active]);
    const to = byId.get(s.id);
    if (from && to) {
      edges.push({ id: `dispatch-${s.id}`, from, to, kind: 'dispatches' });
    }
  });

  // Specialist → skills (calls) + Specialist → MCPs (tools)
  specs.forEach((s) => {
    const from = byId.get(s.id);
    if (!from) return;
    const mcps = (SPEC_TO_MCPS[s.id] ?? []).slice(0, 1);
    const skills = (SPEC_TO_SKILLS[s.id] ?? []).slice(0, 1);
    mcps.forEach((mid) => {
      const to = byId.get(mid);
      if (to) edges.push({ id: `tool-${s.id}-${mid}`, from, to, kind: 'tools' });
    });
    skills.forEach((sid) => {
      const to = byId.get(sid);
      if (to) edges.push({ id: `call-${s.id}-${sid}`, from, to, kind: 'calls' });
    });
  });

  // Gate chain (advisor only)
  if (showGates || active === 'fsi_advisor') {
    // action_specialist → gate:guardrails
    const action = byId.get('action_specialist');
    const g1 = byId.get('gate:guardrails');
    if (action && g1) {
      edges.push({ id: 'gate-entry', from: action, to: g1, kind: 'sequences' });
    }
    for (let i = 0; i < GATE_ORDER.length - 1; i++) {
      const from = byId.get(GATE_ORDER[i]!);
      const to = byId.get(GATE_ORDER[i + 1]!);
      if (from && to) {
        edges.push({
          id: `gate-${i}`,
          from,
          to,
          kind: 'sequences',
        });
      }
    }
  }

  return { nodes: laidOutNodes, edges };
}

// --------------------------------------------------------------------------
// SVG helpers
// --------------------------------------------------------------------------

function bezier(from: LaidOutNode, to: LaidOutNode): string {
  const fx = from.x + NODE_W / 2;
  const fy = from.y + NODE_H_LABEL;
  const tx = to.x + NODE_W / 2;
  const ty = to.y;
  const my = (fy + ty) / 2;
  return `M${fx},${fy} C${fx},${my} ${tx},${my} ${tx},${ty}`;
}

function horizontalLine(from: LaidOutNode, to: LaidOutNode): string {
  // For ghost spine edges — straight horizontal between orchestrators.
  const fx = from.x + NODE_W;
  const fy = from.y + NODE_H_LABEL / 2;
  const tx = to.x;
  const ty = to.y + NODE_H_LABEL / 2;
  return `M${fx},${fy} L${tx},${ty}`;
}

// --------------------------------------------------------------------------
// Store → state resolver (edges state)
// --------------------------------------------------------------------------

function edgeStateFor(
  from: LaidOutNode,
  to: LaidOutNode,
  storeEdges: Record<string, TraversalEdge>,
  storeNodes: Record<string, TraversalNode>,
): 'dim' | 'active' | 'complete' {
  // Real topology edges are keyed `from|to` in the store (see traversal.ts
  // edgeKey). Ghost edges aren't in the store — they stay dim forever.
  const key = `${from.id}|${to.id}`;
  const e = storeEdges[key];
  if (e) return e.state;
  // Gate sequences aren't stored as topology edges keyed identically — we
  // derive them from gate-node state instead.
  if (from.kind === 'gate' || to.kind === 'gate') {
    const target = storeNodes[to.id];
    if (target?.state === 'solid') return 'complete';
    if (target?.state === 'pulse' || target?.state === 'error') return 'active';
  }
  // Dispatches/calls/tools — mirror the child node state so the edge reads
  // active when its downstream node is lit.
  const target = storeNodes[to.id];
  if (target?.state === 'solid') return 'complete';
  if (target?.state === 'pulse' || target?.state === 'error') return 'active';
  return 'dim';
}

function nodeStateFor(
  n: LaidOutNode,
  storeNodes: Record<string, TraversalNode>,
): TraversalNodeState {
  return storeNodes[n.id]?.state ?? 'dim';
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export interface TraversalMapV2Props {
  /** Persona to lay out around. Defaults to the store's activePersona or 'research'. */
  fallbackPersona: Persona;
  /** Show gate chain regardless of persona (advisor is auto). */
  showGates?: boolean;
  /** Deep-link callback on node click. If omitted, clicks are no-op. */
  onNodeClick?: (id: string) => void;
  /** Override subtitle text (eyebrow). */
  subtitle?: string;
  /** Langfuse base URL — when present with correlation id, clicks open the trace. */
  langfuseBaseUrl?: string;
}

export function TraversalMapV2({
  fallbackPersona,
  showGates = false,
  onNodeClick,
  subtitle,
  langfuseBaseUrl,
}: TraversalMapV2Props) {
  const storeNodes = useTraversalStore((s) => s.nodes);
  const storeEdges = useTraversalStore((s) => s.edges);
  const activePersona = useTraversalStore((s) => s.activePersona);
  const turnId = useTraversalStore((s) => s.turnId);
  const correlationId = useSessionStore((s) => s.correlationId);

  const persona = activePersona ?? fallbackPersona;
  const { nodes, edges } = useMemo(
    () => layout(persona, showGates),
    [persona, showGates],
  );

  // Compute map height to fit all placed nodes + padding.
  const mapHeight = useMemo(() => {
    const maxY = nodes.reduce((m, n) => Math.max(m, n.y + NODE_H_LABEL), 0);
    return maxY + 24;
  }, [nodes]);

  const defaultClick = useCallback(
    (nodeId: string) => {
      if (onNodeClick) return onNodeClick(nodeId);
      if (!langfuseBaseUrl || !correlationId) return;
      const base = langfuseBaseUrl.replace(/\/$/, '');
      const url = `${base}/trace/${encodeURIComponent(correlationId)}?span=${encodeURIComponent(nodeId)}`;
      try {
        window.open(url, '_blank', 'noopener,noreferrer');
      } catch {
        /* popup blocked — ignore */
      }
    },
    [onNodeClick, langfuseBaseUrl, correlationId],
  );

  const interactive = Boolean(onNodeClick) || Boolean(langfuseBaseUrl && correlationId);

  const handleKey = (id: string) => (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (!interactive) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      defaultClick(id);
    }
  };

  const traceShort = correlationId ? correlationId.slice(0, 12) : null;
  const specCount = nodes.filter((n) => n.kind === 'specialist').length;

  const computedSubtitle =
    subtitle ??
    [
      `persona: ${({ fsi_research: 'research', fsi_advisor: 'advisor', fsi_client_liaison: 'liaison' } as const)[persona]}`,
      specCount > 0 ? `${specCount} specialists` : null,
      turnId ? `turn ${turnId.slice(0, 8)}` : null,
      traceShort ? `trace ${traceShort}` : null,
    ]
      .filter(Boolean)
      .join(' · ');

  return (
    <div className="v2-map" data-persona={persona} data-testid="traversal-map-v2">
      <div className="v2-map__header">
        <div className="v2-map__title">
          <span className="v2-map__title-main">Architecture Map</span>
          <span className="v2-map__title-sub">{computedSubtitle}</span>
        </div>
        <div className="v2-map__legend" aria-hidden="false">
          <span className="v2-map__legend-item"><span className="v2-map__legend-dot" data-state="dim"></span>dim</span>
          <span className="v2-map__legend-item"><span className="v2-map__legend-dot" data-state="pulse"></span>in-flight</span>
          <span className="v2-map__legend-item"><span className="v2-map__legend-dot" data-state="solid"></span>complete</span>
          <span className="v2-map__legend-item"><span className="v2-map__legend-dot" data-state="error"></span>error</span>
        </div>
      </div>
      <div className="v2-map__canvas" style={{ minHeight: mapHeight }}>
        <svg
          viewBox={`0 0 ${VIEWBOX_W} ${mapHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="v2-map__svg"
          role="img"
          aria-label="Live architecture traversal map"
        >
          {edges.map((e) => {
            const state =
              e.kind === 'ghost' ? 'dim' : edgeStateFor(e.from, e.to, storeEdges, storeNodes);
            const d = e.kind === 'ghost' ? horizontalLine(e.from, e.to) : bezier(e.from, e.to);
            const className =
              e.kind === 'ghost'
                ? 'v2-map__edge v2-map__edge--ghost'
                : 'v2-map__edge';
            return (
              <path
                key={e.id}
                className={className}
                d={d}
                data-kind={e.kind}
                data-state={state}
                data-testid={`v2-map-edge-${e.id}`}
              />
            );
          })}
        </svg>
        {nodes.map((n) => {
          const state = nodeStateFor(n, storeNodes);
          const storeMeta = storeNodes[n.id];
          const latency = storeMeta?.latency_ms;
          const title = [
            n.chip,
            n.label,
            latency !== undefined ? `${latency}ms` : null,
            storeMeta?.error ? `error: ${storeMeta.error}` : null,
          ]
            .filter(Boolean)
            .join(' · ');
          return (
            <div
              key={n.id}
              className="v2-map__node"
              data-kind={n.kind}
              data-state={state}
              data-persona-tag={n.personaTag}
              data-testid={`v2-map-node-${n.id}`}
              style={{ left: `${(n.x / VIEWBOX_W) * 100}%`, top: n.y, width: NODE_W }}
              role={interactive ? 'button' : undefined}
              tabIndex={interactive ? 0 : -1}
              onClick={interactive ? () => defaultClick(n.id) : undefined}
              onKeyDown={handleKey(n.id)}
              aria-label={`${n.chip} (${n.kind}, ${state})`}
              title={title}
            >
              <div className="v2-map__node-chip">{n.chip}</div>
              <div className="v2-map__node-label">{n.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

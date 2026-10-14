/**
 * TraversalMapV3 — architecture map polish pass (roadmap item #8).
 *
 * Over TraversalMapV2, v3 adds:
 *   1. Hover tooltip on every node: role, model tier, tool allowlist,
 *      memory scope, latest status + latency, and per-node explainer.
 *   2. Collapsible legend with icon per node kind + state color.
 *   3. "This turn only" filter toggle — hides nodes/edges that never fired.
 *   4. Per-persona caption strip below the map explaining what the user is
 *      looking at ("Sarah's research fans out to 4 specialists in parallel").
 *   5. Progressive disclosure — advisor gate chain only renders when a write
 *      plan is in flight (pendingPlan present).
 *   6. Trust-spine band (CSS band replaces v2's ambiguous ghost edges).
 *
 * Wiring: identical to v2. Reads from useTraversalStore + useSessionStore.
 * No new backend contract needed — the polish is 100% presentation-layer.
 */

import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from 'react';
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
// Layout constants (kept aligned with v2 so stores don't need to change)
// --------------------------------------------------------------------------

const VIEWBOX_W = 1240;
const NODE_W = 100;
const NODE_H_LABEL = 34;
const ROW_Y = {
  coord: 8,
  orch: 70,
  spec: 140,
  mcp_skill: 208,
  gate: 280,
};
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
  fsi_research: 'Research Analyst',
  fsi_advisor: 'Wealth Advisor',
  fsi_client_liaison: 'Client Liaison',
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
const TOPOLOGY_BY_ID: Map<string, TopologyNodeRaw> = new Map(
  TOPOLOGY.nodes.map((n) => [n.id, n]),
);

const SPEC_TO_ORCH: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const e of TOPOLOGY.edges) {
    if (e.kind === 'dispatches') out[e.to] = e.from;
  }
  return out;
})();
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

function specialistsFor(persona: Persona): TopologyNodeRaw[] {
  const orchId = ORCH_NODE_ID[persona];
  return TOPOLOGY.nodes
    .filter((n) => n.kind === 'specialist' && SPEC_TO_ORCH[n.id] === orchId)
    .sort((a, b) => a.id.localeCompare(b.id));
}

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
  return GATE_ORDER.map((id) => TOPOLOGY_BY_ID.get(id)).filter(
    (x): x is TopologyNodeRaw => x !== undefined,
  );
}

// --------------------------------------------------------------------------
// Layout
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
  kind: 'routes' | 'dispatches' | 'calls' | 'tools' | 'sequences';
}

function layout(active: Persona, showGates: boolean): {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
} {
  const nodes: LaidOutNode[] = [];
  const byId = new Map<string, LaidOutNode>();

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
  nodes.push(coord);
  byId.set('coordinator', coord);

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
    nodes.push(node);
    byId.set(id, node);
  });

  const specs = specialistsFor(active);
  const specBaseX =
    ORCH_X[active] - ((specs.length - 1) * (NODE_W + 8)) / 2;
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
    nodes.push(node);
    byId.set(s.id, node);
  });

  const placed = new Set<string>(byId.keys());
  specs.forEach((s, idx) => {
    const mcps = (SPEC_TO_MCPS[s.id] ?? []).filter((mid) => {
      const n = TOPOLOGY_BY_ID.get(mid);
      return n && n.kind === 'mcp';
    });
    const skills = (SPEC_TO_SKILLS[s.id] ?? []).filter((sid) => {
      const n = TOPOLOGY_BY_ID.get(sid);
      return n && n.kind === 'skill';
    });
    const picks: Array<{ id: string; kind: 'skill' | 'mcp' }> = [];
    mcps.slice(0, 1).forEach((id) => picks.push({ id, kind: 'mcp' }));
    skills.slice(0, 1).forEach((id) => picks.push({ id, kind: 'skill' }));
    picks.forEach((p, rank) => {
      if (placed.has(p.id)) return;
      const spec = byId.get(specs[idx]!.id)!;
      const y = ROW_Y.mcp_skill + rank * (NODE_H_LABEL + 8);
      const raw = TOPOLOGY_BY_ID.get(p.id)!;
      const node: LaidOutNode = {
        id: p.id,
        x: spec.x,
        y,
        kind: p.kind,
        chip: raw.label.replace(/^skill:/, '').toLowerCase(),
        label: p.kind === 'skill' ? 'skill' : 'MCP',
        personaTag: PERSONA_TAG[active],
        visible: true,
      };
      nodes.push(node);
      byId.set(p.id, node);
      placed.add(p.id);
    });
  });

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
      nodes.push(node);
      byId.set(g.id, node);
    });
  }

  const edges: LaidOutEdge[] = [];
  (Object.keys(ORCH_NODE_ID) as Persona[]).forEach((p) => {
    const target = byId.get(ORCH_NODE_ID[p]);
    if (target) {
      edges.push({ id: `coord-${p}`, from: coord, to: target, kind: 'routes' });
    }
  });
  specs.forEach((s) => {
    const from = byId.get(ORCH_NODE_ID[active]);
    const to = byId.get(s.id);
    if (from && to) {
      edges.push({ id: `dispatch-${s.id}`, from, to, kind: 'dispatches' });
    }
  });
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
  if (showGates || active === 'fsi_advisor') {
    const action = byId.get('action_specialist');
    const g1 = byId.get('gate:guardrails');
    if (action && g1) edges.push({ id: 'gate-entry', from: action, to: g1, kind: 'sequences' });
    for (let i = 0; i < GATE_ORDER.length - 1; i++) {
      const from = byId.get(GATE_ORDER[i]!);
      const to = byId.get(GATE_ORDER[i + 1]!);
      if (from && to) edges.push({ id: `gate-${i}`, from, to, kind: 'sequences' });
    }
  }

  return { nodes, edges };
}

// --------------------------------------------------------------------------
// Client-simple layout (roadmap item #7)
//
// A 5-node horizontal spine for the client persona that hides specialist
// churn. Client sees only the turn of events that matter to them: their
// message → the trust spine → the RM queue.
//
// We still re-use real store node IDs wherever possible so the existing
// state machine lights nodes up from live events. Two synthetic book-ends
// ("client:message" and "rm:queue") carry zero store state; they're pure
// visual context anchors. They derive state from session connectionStatus
// and the queues store (has the turn produced a queue_update? → solid).
// --------------------------------------------------------------------------

function layoutClientSimple(): {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
  width: number;
} {
  // Use a narrower coord space than the full map — 5 nodes with 140-px
  // chips need ~880 px total. SVG viewBox + HTML canvas min-width both
  // track this value.
  const width = 880;
  const y = 80;
  const total = 5;
  const nodeWidth = 140;
  const gap = (width - total * nodeWidth) / (total + 1);

  const defs: Array<{
    id: string;
    kind: string;
    chip: string;
    label: string;
    personaTag: string;
  }> = [
    {
      id: 'client:message',
      kind: 'client',
      chip: 'Your message',
      label: 'CLIENT',
      personaTag: 'client',
    },
    {
      id: ORCH_NODE_ID.fsi_client_liaison,
      kind: 'orchestrator',
      chip: ORCH_LABEL.fsi_client_liaison,
      label: 'AGENT',
      personaTag: 'client',
    },
    {
      id: 'gate:mnpi_filter',
      kind: 'gate',
      chip: 'MNPI screen',
      label: 'POLICY GATE',
      personaTag: 'shared',
    },
    {
      id: 'gate:audit',
      kind: 'gate',
      chip: 'Audit',
      label: 'POLICY GATE',
      personaTag: 'shared',
    },
    {
      id: 'rm:queue',
      kind: 'rm',
      chip: 'RM queue',
      label: 'ADVISOR',
      personaTag: 'advisor',
    },
  ];

  const nodes: LaidOutNode[] = defs.map((d, i) => ({
    id: d.id,
    x: gap + i * (nodeWidth + gap),
    y,
    kind: d.kind,
    chip: d.chip,
    label: d.label,
    personaTag: d.personaTag,
    visible: true,
  }));

  const edges: LaidOutEdge[] = [];
  for (let i = 0; i < nodes.length - 1; i++) {
    edges.push({
      id: `client-spine-${i}`,
      from: nodes[i]!,
      to: nodes[i + 1]!,
      kind: 'sequences',
    });
  }

  return { nodes, edges, width };
}

// --------------------------------------------------------------------------
// Bezier path builder (shared between full and client-simple layouts)
// --------------------------------------------------------------------------

function bezier(from: LaidOutNode, to: LaidOutNode, nodeWidth: number): string {
  const fx = from.x + nodeWidth / 2;
  const fy = from.y + NODE_H_LABEL;
  const tx = to.x + nodeWidth / 2;
  const ty = to.y;
  const my = (fy + ty) / 2;
  // For sequential spine edges (client-simple), midpoint-Y is nearly
  // identical between from and to so the curve collapses to a line. The
  // formula still works — it just renders as a straight segment.
  return `M${fx},${fy} C${fx},${my} ${tx},${my} ${tx},${ty}`;
}

function edgeStateFor(
  from: LaidOutNode,
  to: LaidOutNode,
  storeEdges: Record<string, TraversalEdge>,
  storeNodes: Record<string, TraversalNode>,
): 'dim' | 'active' | 'complete' {
  const key = `${from.id}|${to.id}`;
  const e = storeEdges[key];
  if (e) return e.state;
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
// Per-persona caption text
// --------------------------------------------------------------------------

function captionFor(persona: Persona, specCount: number): string {
  if (persona === 'fsi_research') {
    return `Sarah's Research Analyst pulls in market quotes, SEC filings, news sentiment and financials — ${specCount} specialists running in parallel. Every read is screened for material non-public information before reaching her brief.`;
  }
  if (persona === 'fsi_advisor') {
    return `Marcus's order plan must pass seven policy gates in sequence — Guardrails, MNPI Filter, Compliance, RM Approval, Dual Auth, Broker Submit, Audit — before the broker ever sees it. Every outcome is audited.`;
  }
  return `Eleanor's message goes to the Client Liaison via the coordinator. The liaison logs the inquiry, queues a hand-off to Marcus, and returns an MNPI-safe acknowledgement. The same trust spine that lights up here also lights up for Sarah and Marcus — one graph, three surfaces.`;
}

/** Short, client-friendly caption for the simplified client-view map. */
function captionForClientSimple(): string {
  return `What happens behind Eleanor's message. Your note flows to the Liaison, the trust spine screens it for material non-public information, every step is audited, and a hand-off drops into your advisor's queue. No positions quoted. No recommendations made.`;
}

function shortDefaultCaptionIcon(persona: Persona): string {
  if (persona === 'fsi_research') return 'R';
  if (persona === 'fsi_advisor') return 'A';
  return 'C';
}

// --------------------------------------------------------------------------
// Tooltip content builder
// --------------------------------------------------------------------------

interface TooltipData {
  chip: string;
  kind: string;
  state: TraversalNodeState;
  persona: string;
  model: string | null;
  detail: string;
  tools: string[];
  mcps: string[];
  latencyMs?: number;
  error?: string;
}

function buildTooltip(n: LaidOutNode, storeNode: TraversalNode | undefined): TooltipData {
  const raw = TOPOLOGY_BY_ID.get(n.id);
  const tools: string[] = [];
  const mcps: string[] = [];
  for (const e of TOPOLOGY.edges) {
    if (e.from !== n.id) continue;
    if (e.kind === 'calls') tools.push(e.to.replace(/^skill:/, ''));
    if (e.kind === 'tools') mcps.push(e.to);
  }
  return {
    chip: n.chip,
    kind: n.kind,
    state: storeNode?.state ?? 'dim',
    persona: raw?.persona ?? n.personaTag,
    model: raw?.model ?? null,
    detail: raw?.detail ?? '',
    tools: tools.slice(0, 4),
    mcps: mcps.slice(0, 3),
    latencyMs: storeNode?.latency_ms,
    error: storeNode?.error,
  };
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export interface TraversalMapV3Props {
  fallbackPersona: Persona;
  showGates?: boolean;
  onNodeClick?: (id: string) => void;
  subtitle?: string;
  langfuseBaseUrl?: string;
  /** When true, advisor gate chain renders. Use it to gate the chain on
   * an in-flight pendingPlan (progressive disclosure — roadmap item #8.5). */
  gateChainVisible?: boolean;
  /** Map variant (roadmap item #7 — client map redesign).
   *  - 'full' (default): the regular 3-orch + specialist fanout + optional
   *    gate chain. Used by research, advisor, and the "full" client view.
   *  - 'client-simple': a 5-node horizontal spine designed for the client
   *    surface — Client → Liaison → MNPI filter → Audit → RM queue. Hides
   *    specialist churn the client doesn't need to see. */
  variant?: 'full' | 'client-simple';
}

export function TraversalMapV3({
  fallbackPersona,
  showGates = false,
  onNodeClick,
  subtitle,
  langfuseBaseUrl,
  gateChainVisible = true,
  variant = 'full',
}: TraversalMapV3Props) {
  const storeNodes = useTraversalStore((s) => s.nodes);
  const storeEdges = useTraversalStore((s) => s.edges);
  const activePersona = useTraversalStore((s) => s.activePersona);
  const turnId = useTraversalStore((s) => s.turnId);
  const correlationId = useSessionStore((s) => s.correlationId);

  const persona = activePersona ?? fallbackPersona;

  // Controls state
  const [showLegend, setShowLegend] = useState(variant !== 'client-simple');
  const [filterThisTurn, setFilterThisTurn] = useState(false);

  const effectiveShowGates = (showGates || persona === 'fsi_advisor') && gateChainVisible;
  const { nodes, edges, viewBoxWidth } = useMemo(() => {
    if (variant === 'client-simple') {
      const r = layoutClientSimple();
      return { nodes: r.nodes, edges: r.edges, viewBoxWidth: r.width };
    }
    const r = layout(persona, effectiveShowGates);
    return { nodes: r.nodes, edges: r.edges, viewBoxWidth: VIEWBOX_W };
  }, [persona, effectiveShowGates, variant]);

  const mapHeight = useMemo(() => {
    const maxY = nodes.reduce((m, n) => Math.max(m, n.y + NODE_H_LABEL), 0);
    return maxY + 24;
  }, [nodes]);

  // Tooltip state
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [tooltip, setTooltip] = useState<{
    data: TooltipData;
    x: number;
    y: number;
  } | null>(null);

  const showTooltip = useCallback(
    (n: LaidOutNode, evt: ReactMouseEvent<HTMLDivElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const storeNode = storeNodes[n.id];
      setTooltip({
        data: buildTooltip(n, storeNode),
        x: evt.clientX - rect.left + 12,
        y: evt.clientY - rect.top + 12,
      });
    },
    [storeNodes],
  );
  const hideTooltip = useCallback(() => setTooltip(null), []);

  const defaultClick = useCallback(
    (nodeId: string) => {
      if (onNodeClick) return onNodeClick(nodeId);
      if (!langfuseBaseUrl || !correlationId) return;
      const base = langfuseBaseUrl.replace(/\/$/, '');
      const url = `${base}/trace/${encodeURIComponent(correlationId)}?span=${encodeURIComponent(nodeId)}`;
      try {
        window.open(url, '_blank', 'noopener,noreferrer');
      } catch {
        /* ignore */
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

  const specCount = nodes.filter((n) => n.kind === 'specialist').length;
  const traceShort = correlationId ? correlationId.slice(0, 12) : null;
  const computedSubtitle =
    subtitle ??
    (variant === 'client-simple'
      ? [
          'simplified view',
          turnId ? `turn ${turnId.slice(0, 8)}` : null,
          traceShort ? `trace ${traceShort}` : null,
        ]
          .filter(Boolean)
          .join(' · ')
      : [
          `persona: ${({ fsi_research: 'research', fsi_advisor: 'advisor', fsi_client_liaison: 'liaison' } as const)[persona]}`,
          specCount > 0 ? `${specCount} specialists` : null,
          turnId ? `turn ${turnId.slice(0, 8)}` : null,
          traceShort ? `trace ${traceShort}` : null,
        ]
          .filter(Boolean)
          .join(' · '));

  const captionText =
    variant === 'client-simple'
      ? captionForClientSimple()
      : captionFor(persona, specCount);
  const captionIcon = shortDefaultCaptionIcon(persona);

  return (
    <div
      className="v3-map"
      data-persona={persona}
      data-variant={variant}
      data-filter={filterThisTurn ? 'this-turn' : 'all'}
      data-testid="traversal-map-v3"
    >
      <div className="v3-map__header">
        <div className="v3-map__title">
          <span className="v3-map__title-main">
            {variant === 'client-simple' ? 'What happens to your message' : 'Architecture Map'}
          </span>
          <span className="v3-map__title-sub">{computedSubtitle}</span>
        </div>
        <div className="v3-map__controls">
          <button
            type="button"
            className="v3-map__toggle"
            aria-pressed={filterThisTurn}
            onClick={() => setFilterThisTurn((v) => !v)}
            title="Hide nodes and edges that haven't fired on the current turn"
          >
            this-turn only
          </button>
          <button
            type="button"
            className="v3-map__toggle"
            aria-pressed={showLegend}
            onClick={() => setShowLegend((v) => !v)}
            title="Toggle the kind + state legend"
          >
            legend
          </button>
        </div>
      </div>

      {showLegend && (
        <div className="v3-map__legend" aria-label="Architecture map legend">
          <div className="v3-map__legend-group">
            <span className="v3-map__legend-title">kind</span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="coordinator"></span>coord
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="orchestrator"></span>orch
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="specialist"></span>specialist
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="skill"></span>skill
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="mcp"></span>mcp
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-icon" data-kind="gate"></span>gate
            </span>
          </div>
          <div className="v3-map__legend-group">
            <span className="v3-map__legend-title">state</span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-dot" data-state="dim"></span>dim
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-dot" data-state="pulse"></span>in-flight
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-dot" data-state="solid"></span>complete
            </span>
            <span className="v3-map__legend-item">
              <span className="v3-map__legend-dot" data-state="error"></span>error
            </span>
          </div>
        </div>
      )}

      <div ref={canvasRef} className="v3-map__canvas" style={{ minHeight: mapHeight }}>
        {variant === 'full' && (
          <div className="v3-map__spine" aria-hidden="true">
            <span className="v3-map__spine-label">· one trust spine ·</span>
          </div>
        )}
        <svg
          viewBox={`0 0 ${viewBoxWidth} ${mapHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="v3-map__svg"
          role="img"
          aria-label="Live architecture traversal map"
        >
          {edges.map((e) => {
            const state = edgeStateFor(e.from, e.to, storeEdges, storeNodes);
            const d = bezier(e.from, e.to, variant === 'client-simple' ? 140 : NODE_W);
            return (
              <path
                key={e.id}
                className="v3-map__edge"
                d={d}
                data-kind={e.kind}
                data-state={state}
                data-testid={`v3-map-edge-${e.id}`}
              />
            );
          })}
        </svg>
        {nodes.map((n) => {
          const state = nodeStateFor(n, storeNodes);
          const storeMeta = storeNodes[n.id];
          const title = [
            n.chip,
            n.label,
            storeMeta?.latency_ms !== undefined ? `${storeMeta.latency_ms}ms` : null,
            storeMeta?.error ? `error: ${storeMeta.error}` : null,
          ]
            .filter(Boolean)
            .join(' · ');
          return (
            <div
              key={n.id}
              className="v3-map__node"
              data-kind={n.kind}
              data-state={state}
              data-persona-tag={n.personaTag}
              data-testid={`v3-map-node-${n.id}`}
              style={{
                left: `${(n.x / viewBoxWidth) * 100}%`,
                top: n.y,
                width: variant === 'client-simple' ? 140 : NODE_W,
              }}
              role={interactive ? 'button' : 'region'}
              tabIndex={interactive ? 0 : -1}
              onClick={interactive ? () => defaultClick(n.id) : undefined}
              onKeyDown={handleKey(n.id)}
              onMouseEnter={(evt) => showTooltip(n, evt)}
              onMouseLeave={hideTooltip}
              onMouseMove={(evt) => showTooltip(n, evt)}
              aria-label={`${n.chip} (${n.kind}, ${state})`}
              title={title}
            >
              <div className="v3-map__node-chip">{n.chip}</div>
              <div className="v3-map__node-label">{n.label}</div>
            </div>
          );
        })}

        {tooltip && (
          <div
            className="v3-map__tooltip"
            role="tooltip"
            style={{
              left: tooltip.x,
              top: tooltip.y,
            }}
          >
            <div className="v3-map__tooltip-title">
              <span>{tooltip.data.chip}</span>
              <span className="v3-map__tooltip-kind">{tooltip.data.kind}</span>
              <span className="v3-map__tooltip-state" data-state={tooltip.data.state}>
                {tooltip.data.state === 'pulse' ? 'in-flight' : tooltip.data.state}
              </span>
            </div>
            {tooltip.data.detail && (
              <div style={{ fontSize: 11, color: 'var(--forensic-text-2)', marginBottom: 6 }}>
                {tooltip.data.detail}
              </div>
            )}
            {tooltip.data.model && (
              <div className="v3-map__tooltip-row">
                <span className="v3-map__tooltip-key">model</span>
                <span className="v3-map__tooltip-val">{tooltip.data.model}</span>
              </div>
            )}
            <div className="v3-map__tooltip-row">
              <span className="v3-map__tooltip-key">persona</span>
              <span className="v3-map__tooltip-val">{tooltip.data.persona}</span>
            </div>
            {tooltip.data.tools.length > 0 && (
              <div className="v3-map__tooltip-row">
                <span className="v3-map__tooltip-key">tools</span>
                <span className="v3-map__tooltip-val">{tooltip.data.tools.join(', ')}</span>
              </div>
            )}
            {tooltip.data.mcps.length > 0 && (
              <div className="v3-map__tooltip-row">
                <span className="v3-map__tooltip-key">mcps</span>
                <span className="v3-map__tooltip-val">{tooltip.data.mcps.join(', ')}</span>
              </div>
            )}
            {tooltip.data.latencyMs !== undefined && (
              <div className="v3-map__tooltip-row">
                <span className="v3-map__tooltip-key">last fire</span>
                <span className="v3-map__tooltip-val">{tooltip.data.latencyMs}ms</span>
              </div>
            )}
            {tooltip.data.error && (
              <div className="v3-map__tooltip-row">
                <span className="v3-map__tooltip-key">error</span>
                <span
                  className="v3-map__tooltip-val"
                  style={{ color: 'var(--error-300)' }}
                >
                  {tooltip.data.error}
                </span>
              </div>
            )}
            {interactive && (
              <div className="v3-map__tooltip-hint">click → open in Langfuse trace</div>
            )}
          </div>
        )}
      </div>

      <div className="v3-map__caption" role="note">
        <span className="v3-map__caption-icon" aria-hidden="true">
          {captionIcon}
        </span>
        <span className="v3-map__caption-text">{captionText}</span>
      </div>
    </div>
  );
}

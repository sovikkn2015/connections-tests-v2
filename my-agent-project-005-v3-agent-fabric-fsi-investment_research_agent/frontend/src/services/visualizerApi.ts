/**
 * Visualizer API — fetches real-time agent-to-tool call traces.
 *
 * Primary source: Anypoint Agent Visualizer traces API.
 * Fallback source: Langfuse traces (reshaped to the visualizer shape) —
 *   used when the Anypoint API isn't configured yet (GATEWAY subagent still
 *   provisioning) or when the installed CLI/SDK doesn't expose a traces API.
 *
 * The UI component never needs to know which source it's looking at.
 */

import { __internal } from './agentApi';

const ANYPOINT_API = import.meta.env.VITE_ANYPOINT_VISUALIZER_API || '';
const ANYPOINT_ORG_ID = import.meta.env.VITE_ANYPOINT_ORG_ID || '';
const LANGFUSE_HOST = import.meta.env.VITE_LANGFUSE_HOST || '';
const LANGFUSE_PUBLIC_KEY = import.meta.env.VITE_LANGFUSE_PUBLIC_KEY || '';
const AGENT_ID_HEADER = import.meta.env.VITE_AGENT_ID || 'ir-research-orchestrator';

/* ── Wire types ── */

export type VisualizerNodeKind = 'user' | 'agent' | 'gateway' | 'mcp' | 'data' | 'response';

export interface VisualizerNode {
  id: string;
  kind: VisualizerNodeKind;
  label: string;
  /** Optional sub-label, e.g. the MCP tool name or agent ID */
  detail?: string;
}

export interface VisualizerEdge {
  from: string;
  to: string;
  /** Latency in ms (end-to-end for this hop). */
  latencyMs?: number;
  /** Policies triggered on this hop (e.g. "mnpi-filter", "rate-limit"). */
  policies?: VisualizerPolicyAnnotation[];
  /** HTTP status (4xx/5xx flag problems). */
  status?: number;
}

export interface VisualizerPolicyAnnotation {
  name: string;
  /** Was the policy applied cleanly, did it redact, or did it block? */
  outcome: 'allowed' | 'redacted' | 'blocked' | 'throttled' | 'open' | 'closed' | 'half-open';
  /** Free-text detail shown on hover ("42 requests remaining in window"). */
  detail?: string;
}

export interface VisualizerGraph {
  nodes: VisualizerNode[];
  edges: VisualizerEdge[];
  /** Correlation ID (thread) this graph represents — lets the UI dedupe. */
  correlationId: string;
  /** When the trace was generated. */
  observedAt: string;
}

export interface VisualizerEvent {
  id: string;
  timestamp: string;
  correlationId: string;
  agentId: string;
  /** e.g. "mcp.call.start", "policy.mnpi.redacted", "circuit.open" */
  kind: string;
  /** Short human-readable description. */
  message: string;
  /** Optional latency the event wraps. */
  latencyMs?: number;
  /** Optional structured metadata. */
  metadata?: Record<string, unknown>;
}

export interface VisualizerSnapshot {
  graph: VisualizerGraph;
  events: VisualizerEvent[];
  /** Which backend produced the snapshot — mostly for the UI footer. */
  source: 'anypoint' | 'langfuse' | 'stub';
}

/* ── Empty/stub snapshot — used before the first trace arrives ── */

export function emptySnapshot(): VisualizerSnapshot {
  const nodes: VisualizerNode[] = [
    { id: 'user', kind: 'user', label: 'Analyst' },
    { id: 'agentforce', kind: 'agent', label: 'Agentforce', detail: AGENT_ID_HEADER },
    { id: 'gateway', kind: 'gateway', label: 'Flex Gateway', detail: 'Agent Fabric' },
    { id: 'mcp', kind: 'mcp', label: 'MCP Server', detail: 'awaiting call' },
    { id: 'data', kind: 'data', label: 'Data Source', detail: '—' },
    { id: 'response', kind: 'response', label: 'Response' },
  ];
  const edges: VisualizerEdge[] = [
    { from: 'user', to: 'agentforce' },
    { from: 'agentforce', to: 'gateway' },
    { from: 'gateway', to: 'mcp' },
    { from: 'mcp', to: 'data' },
    { from: 'data', to: 'response' },
  ];
  return {
    graph: {
      nodes,
      edges,
      correlationId: __internal.getCorrelationId(),
      observedAt: new Date().toISOString(),
    },
    events: [],
    source: 'stub',
  };
}

/* ── Anypoint fetch (primary) ──
 *
 * Anypoint Agent Visualizer exposes a REST endpoint per correlation ID. The
 * exact shape is still evolving; we shape our call defensively and coerce the
 * response. If the endpoint isn't available we throw and let the caller fall
 * back to Langfuse.
 */

interface AnypointTraceResponse {
  correlationId?: string;
  observedAt?: string;
  nodes?: Array<{
    id: string;
    kind: VisualizerNodeKind;
    label: string;
    detail?: string;
  }>;
  edges?: Array<{
    from: string;
    to: string;
    latencyMs?: number;
    status?: number;
    policies?: VisualizerPolicyAnnotation[];
  }>;
  events?: Array<{
    id: string;
    timestamp: string;
    correlationId: string;
    agentId?: string;
    kind: string;
    message: string;
    latencyMs?: number;
    metadata?: Record<string, unknown>;
  }>;
}

async function fetchAnypointSnapshot(correlationId: string): Promise<VisualizerSnapshot> {
  if (!ANYPOINT_API) {
    throw new Error('VITE_ANYPOINT_VISUALIZER_API not configured');
  }
  const url = `${ANYPOINT_API.replace(/\/$/, '')}/traces/${encodeURIComponent(correlationId)}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      'X-Correlation-Id': correlationId,
      'X-Agent-Id': AGENT_ID_HEADER,
      ...(ANYPOINT_ORG_ID ? { 'X-Anypoint-Organization-Id': ANYPOINT_ORG_ID } : {}),
    },
  });
  if (!res.ok) throw new Error(`Anypoint traces: ${res.status}`);
  const data: AnypointTraceResponse = await res.json();

  // Coerce to our shape — Anypoint's schema may drift across CLI versions.
  const nodes = data.nodes?.length ? data.nodes : emptySnapshot().graph.nodes;
  const edges = data.edges?.length ? data.edges : emptySnapshot().graph.edges;
  const events: VisualizerEvent[] = (data.events ?? []).map((e) => ({
    id: e.id,
    timestamp: e.timestamp,
    correlationId: e.correlationId,
    agentId: e.agentId ?? AGENT_ID_HEADER,
    kind: e.kind,
    message: e.message,
    latencyMs: e.latencyMs,
    metadata: e.metadata,
  }));

  return {
    graph: {
      nodes,
      edges,
      correlationId: data.correlationId ?? correlationId,
      observedAt: data.observedAt ?? new Date().toISOString(),
    },
    events,
    source: 'anypoint',
  };
}

/* ── Langfuse fetch (fallback) ──
 *
 * Langfuse has a traces API (/api/public/traces) that returns observations.
 * We shape those into visualizer-like events. This runs from the browser so
 * we only ever use the PUBLIC key — no secrets.
 */

interface LangfuseObservation {
  id: string;
  type: string;
  name?: string;
  startTime?: string;
  endTime?: string;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
}

interface LangfuseTrace {
  id: string;
  name?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
  observations?: LangfuseObservation[];
}

async function fetchLangfuseSnapshot(correlationId: string): Promise<VisualizerSnapshot> {
  if (!LANGFUSE_HOST || !LANGFUSE_PUBLIC_KEY || LANGFUSE_PUBLIC_KEY === 'YOUR_LANGFUSE_PUBLIC_KEY') {
    throw new Error('Langfuse not configured');
  }
  const url = `${LANGFUSE_HOST.replace(/\/$/, '')}/api/public/traces?tags=${encodeURIComponent(correlationId)}&limit=1`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Basic ${btoa(`${LANGFUSE_PUBLIC_KEY}:`)}`,
      Accept: 'application/json',
    },
  });
  if (!res.ok) throw new Error(`Langfuse traces: ${res.status}`);
  const body = await res.json();
  const trace: LangfuseTrace | undefined = Array.isArray(body.data) ? body.data[0] : undefined;
  if (!trace) return emptySnapshot();

  const events: VisualizerEvent[] = (trace.observations ?? []).map((o) => {
    const start = o.startTime ? Date.parse(o.startTime) : undefined;
    const end = o.endTime ? Date.parse(o.endTime) : undefined;
    return {
      id: o.id,
      timestamp: o.startTime ?? trace.timestamp ?? new Date().toISOString(),
      correlationId,
      agentId: AGENT_ID_HEADER,
      kind: `langfuse.${o.type}`,
      message: o.name ?? o.type,
      latencyMs: start && end ? end - start : undefined,
      metadata: o.metadata,
    };
  });

  // Build a lightweight graph from the observation names: observations that
  // mention "mcp" or a tool name become the MCP step's detail.
  const base = emptySnapshot().graph;
  const mcpNode = base.nodes.find((n) => n.kind === 'mcp');
  const mcpCall = trace.observations?.find((o) => /mcp|tool/i.test(o.name ?? ''));
  if (mcpNode && mcpCall?.name) mcpNode.detail = mcpCall.name;

  return {
    graph: {
      ...base,
      correlationId,
      observedAt: trace.timestamp ?? new Date().toISOString(),
    },
    events,
    source: 'langfuse',
  };
}

/* ── Public API ── */

/**
 * Fetch a visualizer snapshot for a given correlation ID. Prefers Anypoint,
 * falls back to Langfuse, then to the static empty snapshot.
 * Never throws — the UI always receives something renderable.
 */
export async function fetchSnapshot(correlationId?: string): Promise<VisualizerSnapshot> {
  const cid = correlationId || __internal.getCorrelationId();
  try {
    return await fetchAnypointSnapshot(cid);
  } catch (anypointErr) {
    // eslint-disable-next-line no-console
    console.info('[Visualizer] Anypoint unavailable, falling back to Langfuse:', (anypointErr as Error).message);
  }
  try {
    return await fetchLangfuseSnapshot(cid);
  } catch (lfErr) {
    // eslint-disable-next-line no-console
    console.info('[Visualizer] Langfuse unavailable, using empty snapshot:', (lfErr as Error).message);
  }
  const stub = emptySnapshot();
  return { ...stub, graph: { ...stub.graph, correlationId: cid } };
}

/**
 * Poll for fresh snapshots. Callback fires every `intervalMs`. Returns a stop
 * function. Stops polling automatically if the component unmounts and calls it.
 */
export function pollSnapshots(
  onSnapshot: (snap: VisualizerSnapshot) => void,
  intervalMs = 3000,
): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const tick = async () => {
    if (stopped) return;
    const snap = await fetchSnapshot();
    if (stopped) return;
    onSnapshot(snap);
    timer = setTimeout(tick, intervalMs);
  };

  tick();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}

/* ── Test exports ── */
export const __testing = {
  fetchAnypointSnapshot,
  fetchLangfuseSnapshot,
  emptySnapshot,
};

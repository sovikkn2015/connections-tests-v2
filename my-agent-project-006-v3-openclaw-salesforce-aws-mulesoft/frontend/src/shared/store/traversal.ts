/**
 * Zustand store driving the live Architecture Map for the current turn.
 *
 * Nodes and edges start `dim`. Inbound WS events transition agents and
 * skill/MCP targets through pulse → solid (or error). Gate events drive a
 * set of virtual `gate:<name>` nodes and keep `action_specialist` lit while
 * the seven-gate spine is progressing.
 */

import { create } from 'zustand';
import type { Persona } from '../types/persona';
import type { GateName, GateStatus } from '../types/api';
import { resolveNodeId } from '../data/toolToNode';
import topology from '../data/topology.json';

// ----------------------------------------------------------------------------
// Types — re-exported from shared/types/topology so both v1 and v2
// renderers can depend on the same shapes.
// ----------------------------------------------------------------------------

export type {
  TraversalNodeState,
  TraversalEdgeState,
  TraversalNode,
  TraversalEdge,
} from '../types/topology';
import type {
  TraversalNodeState,
  TraversalEdgeState,
  TraversalNode,
  TraversalEdge,
} from '../types/topology';

interface TopologyNodeLike {
  id: string;
  kind: string;
  persona: string;
}
interface TopologyEdgeLike {
  from: string;
  to: string;
  kind: string;
}
interface TopologyJsonLike {
  nodes: TopologyNodeLike[];
  edges: TopologyEdgeLike[];
}

const TOPOLOGY: TopologyJsonLike = topology;

/** Unique edge key — from|to — matches `edgeKey()`. */
function edgeKey(from: string, to: string): string {
  return `${from}|${to}`;
}

/** Build a map: childId -> list of (parentId, edgeKey) so we can activate the upstream edge. */
const PARENT_EDGES: Record<string, { from: string; key: string }[]> = (() => {
  const out: Record<string, { from: string; key: string }[]> = {};
  for (const e of TOPOLOGY.edges) {
    const existing = out[e.to] ?? [];
    existing.push({ from: e.from, key: edgeKey(e.from, e.to) });
    out[e.to] = existing;
  }
  return out;
})();

function findEdge(from: string, to: string): string | null {
  const key = edgeKey(from, to);
  return TOPOLOGY.edges.some((e) => edgeKey(e.from, e.to) === key) ? key : null;
}

// ----------------------------------------------------------------------------
// Store interface
// ----------------------------------------------------------------------------

export interface TraversalState {
  turnId: string | null;
  nodes: Record<string, TraversalNode>;
  edges: Record<string, TraversalEdge>;
  activePersona: Persona | null;
  startedAt: number | null;
  /** Internal: span_id -> resolved node id (for toolCallEnd to find the target). */
  spanToNode: Record<string, string>;
  /** Internal: span_id -> agent_id (to settle the parent edge on completion). */
  spanToAgent: Record<string, string>;

  startTurn: (turnId: string, persona: Persona) => void;
  markAgentActive: (agentId: string) => void;
  toolCallStart: (agentId: string, toolName: string, spanId: string) => void;
  toolCallEnd: (
    spanId: string,
    status: 'ok' | 'error',
    latencyMs: number,
    error?: string,
  ) => void;
  gateEvent: (gate: GateName, status: GateStatus) => void;
  completeTurn: () => void;
  reset: () => void;
}

// ----------------------------------------------------------------------------
// Initial state builders
// ----------------------------------------------------------------------------

function buildInitialNodes(): Record<string, TraversalNode> {
  const nodes: Record<string, TraversalNode> = {};
  for (const n of TOPOLOGY.nodes) {
    nodes[n.id] = { id: n.id, state: 'dim' };
  }
  return nodes;
}

function buildInitialEdges(): Record<string, TraversalEdge> {
  const edges: Record<string, TraversalEdge> = {};
  for (const e of TOPOLOGY.edges) {
    edges[edgeKey(e.from, e.to)] = { from: e.from, to: e.to, state: 'dim' };
  }
  return edges;
}

function nodeStateFromGate(status: GateStatus): TraversalNodeState {
  switch (status) {
    case 'pending':
      return 'dim';
    case 'in_progress':
      return 'pulse';
    case 'passed':
      return 'solid';
    case 'failed':
      return 'error';
    case 'skipped':
      return 'dim';
  }
}

/**
 * Decide a node's next state when transitioning from its current state toward
 * `target`. Prevents a `pulse → solid` completion from being clobbered by a
 * later `pulse` request; once something has errored, it stays errored.
 */
function advance(current: TraversalNodeState, target: TraversalNodeState): TraversalNodeState {
  if (current === 'error') return 'error';
  if (current === 'solid' && target === 'pulse') return 'solid';
  return target;
}

// ----------------------------------------------------------------------------
// Store
// ----------------------------------------------------------------------------

export const useTraversalStore = create<TraversalState>((set) => ({
  turnId: null,
  nodes: buildInitialNodes(),
  edges: buildInitialEdges(),
  activePersona: null,
  startedAt: null,
  spanToNode: {},
  spanToAgent: {},

  startTurn: (turnId, persona) =>
    set({
      turnId,
      nodes: buildInitialNodes(),
      edges: buildInitialEdges(),
      activePersona: persona,
      startedAt: Date.now(),
      spanToNode: {},
      spanToAgent: {},
    }),

  markAgentActive: (agentId) =>
    set((s) => {
      const node = s.nodes[agentId];
      if (!node) return s;
      const nextNodes: Record<string, TraversalNode> = {
        ...s.nodes,
        [agentId]: { ...node, state: advance(node.state, 'pulse') },
      };
      const nextEdges = { ...s.edges };
      const parents = PARENT_EDGES[agentId] ?? [];
      for (const p of parents) {
        const e = nextEdges[p.key];
        if (e && e.state === 'dim') nextEdges[p.key] = { ...e, state: 'active' };
      }
      return { nodes: nextNodes, edges: nextEdges };
    }),

  toolCallStart: (agentId, toolName, spanId) =>
    set((s) => {
      // Resolve persona hint from the topology entry for agentId (if known).
      const agentEntry = TOPOLOGY.nodes.find((n) => n.id === agentId);
      const personaHint =
        agentEntry && agentEntry.persona !== 'shared'
          ? (agentEntry.persona as Persona)
          : undefined;
      const targetId = resolveNodeId(toolName, personaHint);
      if (!targetId || !s.nodes[targetId]) {
        // Unknown tool — still light the caller so we don't break the trail.
        const caller = s.nodes[agentId];
        if (!caller) return s;
        return {
          nodes: {
            ...s.nodes,
            [agentId]: { ...caller, state: advance(caller.state, 'pulse') },
          },
        };
      }

      const target = s.nodes[targetId];
      const nextNodes: Record<string, TraversalNode> = {
        ...s.nodes,
        [targetId]: { ...target, state: advance(target.state, 'pulse') },
      };
      // Also pulse the caller — it's definitely active if it's emitting calls.
      const caller = s.nodes[agentId];
      if (caller) {
        nextNodes[agentId] = { ...caller, state: advance(caller.state, 'pulse') };
      }

      const nextEdges = { ...s.edges };
      const agentToTarget = findEdge(agentId, targetId);
      if (agentToTarget) {
        const e = nextEdges[agentToTarget];
        if (e && e.state !== 'complete') nextEdges[agentToTarget] = { ...e, state: 'active' };
      }
      // Also pulse the orchestrator→agent edge (parent of the caller).
      const parents = PARENT_EDGES[agentId] ?? [];
      for (const p of parents) {
        const e = nextEdges[p.key];
        if (e && e.state === 'dim') nextEdges[p.key] = { ...e, state: 'active' };
      }

      return {
        nodes: nextNodes,
        edges: nextEdges,
        spanToNode: { ...s.spanToNode, [spanId]: targetId },
        spanToAgent: { ...s.spanToAgent, [spanId]: agentId },
      };
    }),

  toolCallEnd: (spanId, status, latencyMs, error) =>
    set((s) => {
      const targetId = s.spanToNode[spanId];
      const agentId = s.spanToAgent[spanId];
      if (!targetId || !s.nodes[targetId]) return s;
      const target = s.nodes[targetId];
      const finalState: TraversalNodeState = status === 'ok' ? 'solid' : 'error';
      const nextNodes: Record<string, TraversalNode> = {
        ...s.nodes,
        [targetId]: {
          ...target,
          state: finalState,
          latency_ms: latencyMs,
          error: error ?? target.error,
        },
      };
      const nextEdges = { ...s.edges };
      if (agentId) {
        const key = findEdge(agentId, targetId);
        if (key && nextEdges[key]) {
          nextEdges[key] = { ...nextEdges[key], state: 'complete' };
        }
      }
      return { nodes: nextNodes, edges: nextEdges };
    }),

  gateEvent: (gate, status) =>
    set((s) => {
      const gateNodeId = `gate:${gate}`;
      const nextState = nodeStateFromGate(status);
      const prevGate = s.nodes[gateNodeId] ?? { id: gateNodeId, state: 'dim' as const };
      const nextNodes: Record<string, TraversalNode> = {
        ...s.nodes,
        [gateNodeId]: { ...prevGate, state: advance(prevGate.state, nextState) },
      };
      // Light the sequential edge INTO this gate (from action_specialist for
      // gate 1, or from the previous gate in the chain). Derived from the
      // topology's `sequences` edges at module init so there's one source
      // of truth — reorder topology.json and the store follows.
      const gateEdges = TOPOLOGY.edges.filter((e) => e.kind === 'sequences');
      // Map: gateNodeId -> parent node id (action_specialist or the prior gate).
      const PARENT_OF_GATE: Record<string, string> = {};
      for (const e of gateEdges) {
        PARENT_OF_GATE[e.to] = e.from;
      }
      const fromId = PARENT_OF_GATE[gateNodeId];
      if (fromId) {
        const key = edgeKey(fromId, gateNodeId);
        if (s.edges[key]) {
          const desiredState: TraversalEdgeState =
            status === 'passed' || status === 'failed' ? 'complete' : 'active';
          const nextEdges = { ...s.edges, [key]: { ...s.edges[key]!, state: desiredState } };
          // Keep action_specialist lit while gates progress.
          const action = nextNodes.action_specialist;
          if (action) {
            const lightAction: TraversalNodeState =
              status === 'failed'
                ? 'error'
                : status === 'passed' || status === 'in_progress'
                  ? 'pulse'
                  : action.state;
            nextNodes.action_specialist = {
              ...action,
              state: advance(action.state, lightAction),
            };
          }
          return { nodes: nextNodes, edges: nextEdges };
        }
      }
      // Keep action_specialist lit even if we couldn't resolve an edge.
      const action = nextNodes.action_specialist;
      if (action) {
        const lightAction: TraversalNodeState =
          status === 'failed'
            ? 'error'
            : status === 'passed' || status === 'in_progress'
              ? 'pulse'
              : action.state;
        nextNodes.action_specialist = { ...action, state: advance(action.state, lightAction) };
      }
      return { nodes: nextNodes };
    }),

  completeTurn: () => set({ activePersona: null }),

  reset: () =>
    set({
      turnId: null,
      nodes: buildInitialNodes(),
      edges: buildInitialEdges(),
      activePersona: null,
      startedAt: null,
      spanToNode: {},
      spanToAgent: {},
    }),
}));

/** Exposed for tests + panels that need topology awareness without re-reading JSON. */
export function getTopologyNodeIds(): string[] {
  return TOPOLOGY.nodes.map((n) => n.id);
}

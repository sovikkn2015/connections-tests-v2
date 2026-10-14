/**
 * Topology + traversal graph types — shared between v1 and v2 visualisations.
 *
 * These types describe the live architecture-map data model:
 *   - TopologyJson: the static graph (agents, skills, MCPs, gates)
 *     sourced from frontend/src/shared/data/topology.json
 *   - TraversalNode / TraversalEdge: per-turn runtime state painted onto
 *     that graph as WebSocket events arrive (useTraversalStore)
 *
 * Kept in `shared/types/` so any renderer (v1 TraversalMap, v2
 * TraversalMapV2, future alternative views) can depend on the same shapes
 * without reaching across the v1/v2 boundary.
 */

import type { Persona } from './persona';

export type NodeKind =
  | 'coordinator'
  | 'orchestrator'
  | 'specialist'
  | 'skill'
  | 'mcp'
  | 'trust'
  | 'gate';

export type NodePersona = Persona | 'shared';
export type NodeLayer = 0 | 1 | 2 | 3 | 4 | 5;
export type NodeModel = 'sonnet' | 'haiku' | null;

export interface TopologyNode {
  id: string;
  kind: NodeKind;
  label: string;
  persona: NodePersona;
  layer: NodeLayer;
  model: NodeModel;
  detail?: string;
}

export type EdgeKind = 'routes' | 'dispatches' | 'calls' | 'tools' | 'sequences';

export interface TopologyEdge {
  from: string;
  to: string;
  kind: EdgeKind;
}

export interface TopologyJson {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export type TraversalNodeState = 'dim' | 'pulse' | 'solid' | 'error';
export type TraversalEdgeState = 'dim' | 'active' | 'complete';

export interface TraversalNode {
  id: string;
  state: TraversalNodeState;
  latency_ms?: number;
  error?: string;
}

export interface TraversalEdge {
  from: string;
  to: string;
  state: TraversalEdgeState;
}

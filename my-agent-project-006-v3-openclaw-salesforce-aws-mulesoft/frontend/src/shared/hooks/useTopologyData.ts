/**
 * useTopologyData — safe loader for the multi-layer topology JSON produced by
 * builder 1 at `src/data/topology.json`.
 *
 * Shape: 43 nodes / 53 edges for the default 006 v3 topology — 1 coordinator
 * + 3 orchestrators + 11 specialists + 13 skills + 5 MCPs + 7 gates + 3 trust.
 * The 14-agent registry in `openclaw/orchestration/topology.py` is the source
 * of truth; the other kinds are infrastructure rows the export script adds.
 *
 * If the JSON hasn't been generated yet this hook returns a minimal
 * placeholder graph (coordinator + three persona orchestrators) so
 * `<TraversalMap>` renders something useful and the app does not crash.
 *
 * The load runs once at mount and is memoized — the resulting topology is a
 * stable reference across renders so `layoutTopology` memoization works.
 */

import { useEffect, useState } from 'react';
import type { TopologyJson } from '../types/topology';

/** Minimal placeholder — proves the component works before builder 1 lands. */
export const FALLBACK_TOPOLOGY: TopologyJson = {
  nodes: [
    {
      id: 'coordinator',
      kind: 'coordinator',
      label: 'coordinator',
      persona: 'shared',
      layer: 0,
      model: 'sonnet',
      detail: 'placeholder — topology.json not yet published',
    },
    {
      id: 'research_orchestrator',
      kind: 'orchestrator',
      label: 'research_orch',
      persona: 'fsi_research',
      layer: 1,
      model: 'sonnet',
    },
    {
      id: 'advisor_orchestrator',
      kind: 'orchestrator',
      label: 'advisor_orch',
      persona: 'fsi_advisor',
      layer: 1,
      model: 'sonnet',
    },
    {
      id: 'liaison_orchestrator',
      kind: 'orchestrator',
      label: 'liaison_orch',
      persona: 'fsi_client_liaison',
      layer: 1,
      model: 'haiku',
    },
  ],
  edges: [
    { from: 'coordinator', to: 'research_orchestrator', kind: 'routes' },
    { from: 'coordinator', to: 'advisor_orchestrator', kind: 'routes' },
    { from: 'coordinator', to: 'liaison_orchestrator', kind: 'routes' },
  ],
};

export interface UseTopologyDataResult {
  topology: TopologyJson;
  loading: boolean;
  usingFallback: boolean;
}

/**
 * Hook: dynamically import the topology JSON. Returns the fallback immediately
 * so the component never blocks on data. Upgrades to the real topology once
 * the import resolves.
 */
export function useTopologyData(): UseTopologyDataResult {
  const [state, setState] = useState<UseTopologyDataResult>({
    topology: FALLBACK_TOPOLOGY,
    loading: true,
    usingFallback: true,
  });

  useEffect(() => {
    let cancelled = false;
    // Use a runtime-computed specifier so TypeScript doesn't require
    // `src/data/topology.json` to exist at build time (builder 1 owns it).
    const specifier = '../data/topology.json';
    (import(/* @vite-ignore */ specifier) as Promise<{ default?: TopologyJson } & TopologyJson>)
      .then((mod) => {
        if (cancelled) return;
        const real = (mod.default ?? mod) as TopologyJson;
        if (!real || !Array.isArray(real.nodes) || !Array.isArray(real.edges)) {
          // eslint-disable-next-line no-console
          console.warn(
            '[useTopologyData] topology.json present but malformed — staying on fallback',
          );
          setState((s) => ({ ...s, loading: false }));
          return;
        }
        setState({ topology: real, loading: false, usingFallback: false });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (import.meta.env.DEV) {
          // eslint-disable-next-line no-console
          console.warn(
            '[useTopologyData] topology.json not found — using fallback placeholder. ' +
              'This is expected while builder 1 hasn\'t published yet.',
            err,
          );
        }
        setState({ topology: FALLBACK_TOPOLOGY, loading: false, usingFallback: true });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

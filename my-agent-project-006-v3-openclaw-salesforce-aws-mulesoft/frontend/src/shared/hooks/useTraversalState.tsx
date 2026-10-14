/**
 * useTraversalState — safe adapter for builder 1's `useTraversalStore`.
 *
 * Builder 1 owns `src/store/traversal.ts`. At build time that module may or
 * may not exist yet; this adapter dynamically resolves the store once and
 * falls back to a static empty-state view if the import fails.
 *
 * Because React's rules-of-hooks forbid us from conditionally calling a
 * different hook across renders, this file exposes a provider-style API:
 *
 *   <TraversalStateProvider>
 *     {(state) => <TraversalMap {...state} />}
 *   </TraversalStateProvider>
 *
 * The provider picks its render path once per mount: either fallback (no
 * store resolved yet) or live (subscribed via `LiveTraversalBridge`). Once
 * the dynamic import completes, `LiveTraversalBridge` is mounted and its
 * hook identity stays stable for its whole lifetime.
 */

import { useEffect, useState, type ReactNode } from 'react';
import type { Persona } from '../types/persona';
import type { TraversalEdge, TraversalNode } from '../types/topology';

export interface TraversalStateView {
  nodes: Record<string, TraversalNode>;
  edges: Record<string, TraversalEdge>;
  activePersona: Persona | null;
  correlationId?: string | null;
}

export const EMPTY_TRAVERSAL_STATE: TraversalStateView = {
  nodes: {},
  edges: {},
  activePersona: null,
  correlationId: null,
};

type TraversalStoreHook = <T>(selector: (state: TraversalStateView) => T) => T;

type MaybeStoreModule = {
  useTraversalStore?: TraversalStoreHook;
};

/** Module-level cache — builder 1's store is resolved at most once. */
let resolvedStoreHook: TraversalStoreHook | null = null;
let resolvePromise: Promise<TraversalStoreHook | null> | null = null;

function resolveStore(): Promise<TraversalStoreHook | null> {
  if (resolvedStoreHook) return Promise.resolve(resolvedStoreHook);
  if (resolvePromise) return resolvePromise;
  // Use a runtime-computed specifier so TypeScript doesn't require the module
  // to exist at build time. Builder 1 owns `src/store/traversal.ts`; this
  // dynamic import resolves it at runtime if present and otherwise falls
  // through to the catch branch.
  const specifier = '../store/traversal';
  resolvePromise = (import(/* @vite-ignore */ specifier) as Promise<MaybeStoreModule>)
    .then((mod) => {
      if (typeof mod.useTraversalStore === 'function') {
        resolvedStoreHook = mod.useTraversalStore;
        return resolvedStoreHook;
      }
      return null;
    })
    .catch(() => null);
  return resolvePromise;
}

/**
 * Returns `null` on first render (use the fallback) and the hook function
 * once builder 1's store has been discovered. Stable after resolution.
 */
export function useResolvedTraversalStore(): TraversalStoreHook | null {
  // Using the lazy-init form so that React doesn't treat `resolvedStoreHook`
  // (which itself is a function when the store is already loaded) as a lazy
  // initializer. Without the wrapping arrow React calls it with no args,
  // which explodes because the zustand hook wants a selector.
  const [hook, setHook] = useState<TraversalStoreHook | null>(() => resolvedStoreHook);
  useEffect(() => {
    let cancelled = false;
    if (resolvedStoreHook) {
      setHook(() => resolvedStoreHook);
      return;
    }
    resolveStore().then((h) => {
      if (!cancelled && h) setHook(() => h);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return hook;
}

interface ProviderProps {
  children: (state: TraversalStateView) => ReactNode;
}

/**
 * Renders either a fallback sub-tree (static EMPTY_TRAVERSAL_STATE) or a live
 * sub-tree (subscribing to builder 1's store). The choice is driven by
 * `useResolvedTraversalStore()` which flips from null → function exactly
 * once; after the flip the `LiveTraversalBridge` mounts and its hook identity
 * never changes.
 */
export function TraversalStateProvider({ children }: ProviderProps) {
  const hook = useResolvedTraversalStore();
  if (!hook) {
    return <>{children(EMPTY_TRAVERSAL_STATE)}</>;
  }
  return <LiveTraversalBridge hook={hook}>{children}</LiveTraversalBridge>;
}

function LiveTraversalBridge({
  hook,
  children,
}: {
  hook: TraversalStoreHook;
  children: (state: TraversalStateView) => ReactNode;
}) {
  const state = hook((s) => s);
  return <>{children(state)}</>;
}

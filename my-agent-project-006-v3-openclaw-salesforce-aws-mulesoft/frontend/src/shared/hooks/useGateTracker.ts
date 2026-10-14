/**
 * Seven-gate state machine for the write path.
 *
 * Gates fire in canonical order. Each `gate_*` event updates one cell.
 * The tracker renders all seven even before any have started so the user
 * sees the full path and where we are in it.
 */

import { useCallback, useState } from 'react';
import { SEVEN_GATES, type GateName, type GateState, type GateStatus } from '../types/api';
import type { InboundMessage } from '../types/agent';

function emptyGates(): GateState[] {
  return SEVEN_GATES.map((name) => ({ name, status: 'pending' as GateStatus }));
}

export interface UseGateTrackerResult {
  gates: GateState[];
  activePlanId: string | null;
  handleGateEvent: (
    ev: Extract<InboundMessage, { type: 'gate_passed' | 'gate_started' | 'gate_failed' }>,
  ) => void;
  reset: (planId?: string) => void;
}

function applyEvent(
  gates: GateState[],
  gate: GateName,
  next: GateStatus,
  detail?: string,
): GateState[] {
  return gates.map((g) => {
    if (g.name !== gate) return g;
    const now = new Date().toISOString();
    return {
      ...g,
      status: next,
      started_at: g.started_at ?? (next === 'in_progress' ? now : undefined),
      completed_at:
        next === 'passed' || next === 'failed' || next === 'skipped' ? now : g.completed_at,
      detail: detail ?? g.detail,
    };
  });
}

export function useGateTracker(): UseGateTrackerResult {
  const [gates, setGates] = useState<GateState[]>(emptyGates);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);

  const handleGateEvent = useCallback<UseGateTrackerResult['handleGateEvent']>((ev) => {
    setActivePlanId(ev.plan_id);
    setGates((prev) => applyEvent(prev, ev.gate, ev.status, ev.detail));
  }, []);

  const reset = useCallback((planId?: string) => {
    setGates(emptyGates());
    setActivePlanId(planId ?? null);
  }, []);

  return { gates, activePlanId, handleGateEvent, reset };
}

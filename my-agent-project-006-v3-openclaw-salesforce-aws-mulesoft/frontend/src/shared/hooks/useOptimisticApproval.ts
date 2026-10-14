/**
 * Optimistic HITL approval with rollback.
 *
 * Narrative §6: "HITL approval updates UI instantly; backend validation is async;
 * inline toast rolls back on failure." The hook manages the local optimistic
 * state and reconciles against the server's gate_passed / gate_failed events.
 * Four error tiers align with the ErrorEvent.tier field.
 */

import { useCallback, useState } from 'react';
import type { OutboundMessage } from '../types/agent';

export type ApprovalPhase = 'idle' | 'optimistic' | 'confirmed' | 'rolled_back';

export interface ApprovalState {
  phase: ApprovalPhase;
  errorMessage: string | null;
  errorTier: 'transient' | 'degraded' | 'recoverable' | 'fatal' | null;
}

export interface UseOptimisticApprovalOptions {
  send: (msg: OutboundMessage) => void;
  principalId: string;
}

export function useOptimisticApproval(opts: UseOptimisticApprovalOptions) {
  const [state, setState] = useState<ApprovalState>({
    phase: 'idle',
    errorMessage: null,
    errorTier: null,
  });

  const approve = useCallback(
    (planId: string, planHash: string) => {
      setState({ phase: 'optimistic', errorMessage: null, errorTier: null });
      opts.send({
        type: 'hitl_approval',
        plan_id: planId,
        plan_hash: planHash,
        approved: true,
        approver_principal_id: opts.principalId,
      });
    },
    [opts],
  );

  const reject = useCallback(
    (planId: string, planHash: string) => {
      setState({ phase: 'optimistic', errorMessage: null, errorTier: null });
      opts.send({
        type: 'hitl_approval',
        plan_id: planId,
        plan_hash: planHash,
        approved: false,
        approver_principal_id: opts.principalId,
      });
    },
    [opts],
  );

  const confirm = useCallback(() => {
    setState({ phase: 'confirmed', errorMessage: null, errorTier: null });
  }, []);

  const rollback = useCallback((message: string, tier: ApprovalState['errorTier']) => {
    setState({ phase: 'rolled_back', errorMessage: message, errorTier: tier });
  }, []);

  const reset = useCallback(() => {
    setState({ phase: 'idle', errorMessage: null, errorTier: null });
  }, []);

  return { state, approve, reject, confirm, rollback, reset };
}

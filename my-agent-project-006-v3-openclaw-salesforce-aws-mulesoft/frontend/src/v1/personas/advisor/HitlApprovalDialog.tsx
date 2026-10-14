/**
 * Inline HITL approval (NOT a modal — per "no modals, ever" narrative rule).
 * Renders above the conversation panel. Approve/Reject buttons fire optimistic
 * updates; rollback surfaces a tiered error toast on failure.
 */

import type { ActionPlan } from '../../../shared/types/api';
import type { ApprovalState } from '../../../shared/hooks/useOptimisticApproval';

export interface HitlApprovalDialogProps {
  plan: ActionPlan;
  state: ApprovalState;
  onApprove: (planId: string, planHash: string) => void;
  onReject: (planId: string, planHash: string) => void;
  ttlSeconds?: number;
}

export function HitlApprovalDialog({
  plan,
  state,
  onApprove,
  onReject,
  ttlSeconds,
}: HitlApprovalDialogProps) {
  const disabled = state.phase === 'optimistic' || state.phase === 'confirmed';
  return (
    <div className="advisor-hitl" role="region" aria-label="Approval required">
      <div className="advisor-hitl__title">Approval required — {plan.action_type}</div>
      <div style={{ fontSize: '0.875rem' }}>{plan.summary}</div>
      <dl
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '0.25rem 0.5rem',
          margin: '0.5rem 0',
          fontSize: '0.8125rem',
        }}
      >
        <dt style={{ fontWeight: 600 }}>Household</dt>
        <dd style={{ margin: 0 }}>{plan.client_household}</dd>
        <dt style={{ fontWeight: 600 }}>Notional</dt>
        <dd style={{ margin: 0 }}>${plan.notional_usd.toLocaleString()}</dd>
        <dt style={{ fontWeight: 600 }}>Plan hash</dt>
        <dd style={{ margin: 0, fontFamily: 'monospace' }}>{plan.plan_hash.slice(0, 12)}…</dd>
        {plan.requires_dual_auth && (
          <>
            <dt style={{ fontWeight: 600 }}>Dual-Auth</dt>
            <dd style={{ margin: 0 }}>Required (senior compliance)</dd>
          </>
        )}
        {ttlSeconds !== undefined && (
          <>
            <dt style={{ fontWeight: 600 }}>Token TTL</dt>
            <dd style={{ margin: 0 }}>{ttlSeconds}s</dd>
          </>
        )}
      </dl>
      <div className="advisor-hitl__actions">
        <button
          type="button"
          className="slds-button slds-button_brand"
          disabled={disabled}
          onClick={() => onApprove(plan.plan_id, plan.plan_hash)}
        >
          Approve
        </button>
        <button
          type="button"
          className="slds-button slds-button_destructive"
          disabled={disabled}
          onClick={() => onReject(plan.plan_id, plan.plan_hash)}
        >
          Reject
        </button>
      </div>
      {state.phase === 'optimistic' && (
        <div className="v3-skeleton" style={{ marginTop: '0.5rem' }}>
          validating…
        </div>
      )}
      {state.phase === 'rolled_back' && state.errorMessage && (
        <div
          role="alert"
          className="v3-error-toast"
          data-tier={state.errorTier ?? 'recoverable'}
          style={{ marginTop: '0.5rem' }}
        >
          <span>Rolled back: {state.errorMessage}</span>
        </div>
      )}
    </div>
  );
}

/**
 * V4 Inline Action Card — HITL approval styled to the designer's
 * `action-card` classes, wired through the same `useOptimisticApproval`
 * hook v2/v3 use. Same backend contract (plan_id, plan_hash, approve
 * round-trip) — purely a visual skin change.
 *
 * Keyboard: ⌘↵ approve · ⌘⌫ deny. The hint renders in the card footer
 * so RM doesn't have to remember.
 */

import { useEffect } from 'react';
import type { ActionPlan } from '../../shared/types/api';
import type { ApprovalState } from '../../shared/hooks/useOptimisticApproval';

export interface InlineActionCardV4Props {
  plan: ActionPlan;
  state: ApprovalState;
  onApprove: (planId: string, planHash: string) => void;
  onReject: (planId: string, planHash: string) => void;
  onEdit?: () => void;
  diff?: Array<{ label: string; before: string; after: string; ok?: boolean }>;
}

function actionVerb(type: ActionPlan['action_type']): string {
  switch (type) {
    case 'submit_order':
      return 'SUBMIT';
    case 'cancel_order':
      return 'CANCEL';
    case 'modify_order':
      return 'MODIFY';
    case 'initiate_wire':
      return 'WIRE';
  }
}

function formatUsd(n: number): string {
  return '$' + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function InlineActionCardV4({
  plan,
  state,
  onApprove,
  onReject,
  onEdit,
  diff,
}: InlineActionCardV4Props) {
  const disabled = state.phase === 'optimistic' || state.phase === 'confirmed';

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === 'Enter' && !disabled) {
        e.preventDefault();
        onApprove(plan.plan_id, plan.plan_hash);
      } else if (e.key === 'Backspace' && !disabled) {
        e.preventDefault();
        onReject(plan.plan_id, plan.plan_hash);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [disabled, plan, onApprove, onReject]);

  return (
    <div className="action-card" role="region" aria-label="Pending approval">
      <div className="action-card__head">
        <span className="action-card__badge">!</span>
        Pending approval · plan {plan.plan_id.slice(0, 8)}
      </div>
      <div style={{ fontSize: 13, color: 'var(--v4-n-700)', marginBottom: 12 }}>
        {plan.summary}
      </div>
      <div className="action-card__plan">
        <div className="action-card__row">
          <span className="action-card__label">order</span>
          <span className="action-card__value">{actionVerb(plan.action_type)}</span>
        </div>
        <div className="action-card__row">
          <span className="action-card__label">household</span>
          <span className="action-card__value">{plan.client_household}</span>
        </div>
        <div className="action-card__row">
          <span className="action-card__label">notional</span>
          <span className="action-card__value">{formatUsd(plan.notional_usd)}</span>
        </div>
        <div className="action-card__row">
          <span className="action-card__label">dual-auth</span>
          <span className="action-card__value">{plan.requires_dual_auth ? 'required' : 'not required'}</span>
        </div>
        <div className="action-card__row">
          <span className="action-card__label">plan hash</span>
          <span className="action-card__value w360-mono" style={{ fontSize: 10 }}>
            {plan.plan_hash.slice(0, 16)}…
          </span>
        </div>
      </div>
      {diff && diff.length > 0 && (
        <div
          style={{
            background: 'var(--v4-n-050)',
            border: '1px solid var(--v4-n-200)',
            borderRadius: 3,
            padding: '8px 10px',
            marginBottom: 10,
            fontSize: 11.5,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--v4-n-500)',
              marginBottom: 4,
            }}
          >
            Projected impact
          </div>
          {diff.map((d, i) => (
            <div
              key={i}
              className="w360-mono"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '2px 0',
              }}
            >
              <span>{d.label}</span>
              <span>
                {d.before}
                <span style={{ color: 'var(--v4-brand-500)', margin: '0 6px' }}>→</span>
                <span style={{ color: d.ok ? 'var(--v4-success-500)' : undefined }}>{d.after}</span>
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="action-card__actions">
        <button
          type="button"
          className="btn-approve"
          onClick={() => onApprove(plan.plan_id, plan.plan_hash)}
          disabled={disabled}
        >
          Approve & submit
        </button>
        {onEdit && (
          <button type="button" className="btn-edit" onClick={onEdit} disabled={disabled}>
            Edit plan
          </button>
        )}
        <button
          type="button"
          className="btn-deny"
          onClick={() => onReject(plan.plan_id, plan.plan_hash)}
          disabled={disabled}
        >
          Deny
        </button>
        <span className="action-card__kbhint">
          ⌘↵ approve · ⌘⌫ deny{plan.requires_dual_auth ? ' · dual-auth required' : ''}
        </span>
      </div>
      {state.phase === 'rolled_back' && state.errorMessage && (
        <div style={{ color: 'var(--v4-error-500)', marginTop: 8, fontSize: 12 }}>
          {state.errorMessage}
        </div>
      )}
    </div>
  );
}

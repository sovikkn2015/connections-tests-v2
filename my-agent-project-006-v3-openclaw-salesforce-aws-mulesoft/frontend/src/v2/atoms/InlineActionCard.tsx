/**
 * InlineActionCard — HITL approval rendered as an AI message in the
 * conversation, NOT a modal.
 *
 * Uses the existing `useOptimisticApproval` hook (approve/reject, optimistic
 * confirm, rollback) and the `ActionPlan` shape that already flows through
 * `hitl_prompt` WebSocket events. No new backend contracts — just a
 * different presentation surface.
 *
 * Keyboard: ⌘↵ approve, ⌘⌫ deny (advisor expects this per design).
 */

import { useEffect } from 'react';
import type { ActionPlan } from '../../shared/types/api';
import type { ApprovalState } from '../../shared/hooks/useOptimisticApproval';

export interface InlineActionCardProps {
  plan: ActionPlan;
  state: ApprovalState;
  onApprove: (planId: string, planHash: string) => void;
  onReject: (planId: string, planHash: string) => void;
  /** Optional — when provided, "Edit plan" clears the pending card so the RM
   * can re-type with modifications. Omit to hide the Edit button. */
  onEdit?: () => void;
  ttlSeconds?: number;
  /** Optional: projected diff to render beneath the plan table. Can be
   * populated from the brief store or action_specialist output. If omitted
   * the diff section is hidden. */
  diff?: Array<{ label: string; before: string; after: string; ok?: boolean }>;
}

function formatUsd(n: number): string {
  return '$' + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
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

export function InlineActionCard({
  plan,
  state,
  onApprove,
  onReject,
  onEdit,
  ttlSeconds,
  diff,
}: InlineActionCardProps) {
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
    <div className="v2-action-card" role="region" aria-label="Approval required">
      <div className="v2-action-card__head">
        <span
          aria-hidden="true"
          style={{
            display: 'inline-flex',
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: 'var(--w360-brand-500)',
            color: '#fff',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
          }}
        >
          !
        </span>
        Pending approval · plan {plan.plan_id.slice(0, 8)}
      </div>
      <div className="v2-action-card__body">
        <div>{plan.summary}</div>

        <div className="v2-action-card__plan">
          <span className="v2-action-card__label">action</span>
          <span className="v2-action-card__value">{actionVerb(plan.action_type)}</span>
          <span className="v2-action-card__label">household</span>
          <span className="v2-action-card__value">{plan.client_household}</span>
          <span className="v2-action-card__label">notional</span>
          <span className="v2-action-card__value">{formatUsd(plan.notional_usd)}</span>
          <span className="v2-action-card__label">plan hash</span>
          <span className="v2-action-card__value">{plan.plan_hash.slice(0, 12)}…</span>
          {plan.requires_dual_auth && (
            <>
              <span className="v2-action-card__label">dual-auth</span>
              <span className="v2-action-card__value" style={{ color: 'var(--warning-500)' }}>
                required
              </span>
            </>
          )}
          {ttlSeconds !== undefined && (
            <>
              <span className="v2-action-card__label">token TTL</span>
              <span className="v2-action-card__value">{ttlSeconds}s</span>
            </>
          )}
        </div>

        {diff && diff.length > 0 && (
          <div className="v2-action-card__diff">
            <div
              style={{
                fontSize: 10,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--n-500)',
                marginBottom: 4,
              }}
            >
              Impact
            </div>
            {diff.map((d, i) => (
              <div key={i} className="v2-action-card__diff-row">
                <span>{d.label}</span>
                <span style={d.ok === false ? { color: 'var(--error-500)' } : undefined}>
                  {d.before} <span className="v2-action-card__diff-arrow">→</span> {d.after}
                  {d.ok === true && <span style={{ color: 'var(--success-500)', marginLeft: 6 }}>✓</span>}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="v2-action-card__actions">
          <button
            type="button"
            className="btn-approve"
            disabled={disabled}
            onClick={() => onApprove(plan.plan_id, plan.plan_hash)}
          >
            Approve &amp; submit
          </button>
          {onEdit && (
            <button
              type="button"
              className="btn-edit"
              disabled={disabled}
              onClick={onEdit}
              title="Clear this draft and return to drafting — the RM can re-type with modifications"
            >
              Edit plan
            </button>
          )}
          <button
            type="button"
            className="btn-deny"
            disabled={disabled}
            onClick={() => onReject(plan.plan_id, plan.plan_hash)}
          >
            Deny
          </button>
          <span className="v2-action-card__hint">
            ⌘↵ approve · ⌘⌫ deny{plan.requires_dual_auth ? ' · dual-auth required' : ''}
          </span>
        </div>

        {state.phase === 'optimistic' && (
          <div
            style={{
              marginTop: 8,
              fontSize: 11,
              color: 'var(--w360-brand-500)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            validating…
          </div>
        )}
        {state.phase === 'rolled_back' && state.errorMessage && (
          <div
            role="alert"
            style={{
              marginTop: 8,
              padding: '6px 10px',
              background: '#FFF5F5',
              border: '1px solid var(--error-500)',
              borderRadius: 4,
              fontSize: 12,
              color: '#7A1E1E',
            }}
          >
            Rolled back: {state.errorMessage}
          </div>
        )}
      </div>
    </div>
  );
}

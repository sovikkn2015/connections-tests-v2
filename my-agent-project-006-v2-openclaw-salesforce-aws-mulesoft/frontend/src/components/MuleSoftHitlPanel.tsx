/**
 * MuleSoftHitlPanel — modal overlay that renders when the backend emits
 * a `hitl.pending` event over the OpenClaw WebSocket.
 *
 * Wire contract (from the backend — documented in types/index.ts):
 *   IN  { type: "hitl.pending",   token_hash, plan_hash, action, summary_text, ... }
 *   IN  { type: "hitl.completed", token_hash, plan_hash, decision, mulesoft_reference?, ... }
 *   OUT { type: "hitl.decision",  token_hash, decision, approver_note? }
 *
 * Visuals:
 *   - Action type badge (color-coded per action family)
 *   - Human summary text
 *   - Client ID + Account ID
 *   - Live-updating countdown to expires_at
 *   - Dual-auth chip when requires_dual_auth
 *   - Plan details (collapsible JSON viewer — rendered only to the human
 *     approver, never forwarded to any LLM and never logged to console)
 *   - [Approve] / [Reject] buttons + optional approver note
 *   - "Awaiting second approver..." state after first approve on dual-auth
 *   - Terminal banners: Submitted / Rejected / Timed out
 *
 * v2 steering rule 4: this panel talks to OpenClaw WS only (no Agent API,
 * no Apex). rule 21: summary is human-facing. rule 22: token_hash (first 8
 * chars) is logged; the raw token never enters the browser.
 */

import { useEffect, useMemo, useState } from 'react';
import { useAgentStore } from '../store/agentStore';
import type { MuleSoftActionType } from '../types';

type PanelMode = 'preview' | 'reject_note';

const ACTION_BADGE: Record<MuleSoftActionType, { label: string; color: string; bg: string }> = {
  submit_order:         { label: 'TRADE',          color: '#3e3e3c', bg: '#ffedcc' },
  rebalance_portfolio:  { label: 'REBALANCE',      color: '#3e3e3c', bg: '#d8edff' },
  initiate_wire:        { label: 'WIRE',           color: '#fff',    bg: '#c23934' },
  run_kyc_screening:    { label: 'KYC',            color: '#fff',    bg: '#5867e8' },
  open_account:         { label: 'OPEN ACCOUNT',   color: '#fff',    bg: '#04844b' },
  close_account:        { label: 'CLOSE ACCOUNT',  color: '#fff',    bg: '#3e3e3c' },
};

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function MuleSoftHitlPanel() {
  const {
    hitlPendingGate,
    approveHitlPending,
    rejectHitlPending,
    markHitlTimedOut,
  } = useAgentStore();

  const [mode, setMode] = useState<PanelMode>('preview');
  const [note, setNote] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const tokenHash = hitlPendingGate?.event.token_hash;

  // Reset local UI state whenever a new gate arrives (or it clears).
  useEffect(() => {
    setMode('preview');
    setNote('');
    setDetailsOpen(false);
    setSubmitting(false);
  }, [tokenHash]);

  // Live countdown + auto-timeout
  useEffect(() => {
    if (!hitlPendingGate) return;
    const expiresAt = hitlPendingGate.event.expires_at;
    const tick = () => {
      const now = Math.floor(Date.now() / 1000);
      const remaining = Math.max(0, expiresAt - now);
      setSecondsRemaining(remaining);
      if (remaining <= 0 && hitlPendingGate.status === 'waiting_first') {
        markHitlTimedOut(hitlPendingGate.event.token_hash);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [hitlPendingGate, markHitlTimedOut]);

  const badge = useMemo(() => {
    if (!hitlPendingGate) return null;
    return ACTION_BADGE[hitlPendingGate.event.action] ?? {
      label: hitlPendingGate.event.action.toUpperCase(),
      color: '#3e3e3c',
      bg: '#e5e5e5',
    };
  }, [hitlPendingGate]);

  if (!hitlPendingGate || !badge) return null;

  const { event, status, reason, mulesoftReference, auditLogId } = hitlPendingGate;

  const handleApprove = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await approveHitlPending(event.token_hash, note || undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await rejectHitlPending(event.token_hash, note || 'Rejected by approver');
    } finally {
      setSubmitting(false);
    }
  };

  const expired = secondsRemaining <= 0;
  const terminal = status === 'approved' || status === 'rejected' || status === 'timed_out' || status === 'error';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hitl-panel-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(22, 50, 92, 0.45)',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: '4rem 1rem 1rem 1rem',
        overflowY: 'auto',
      }}
    >
      <div
        className="slds-card"
        style={{
          width: 'min(640px, 100%)',
          background: '#fff',
          borderRadius: 6,
          boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
          borderTop: `4px solid ${badge.bg}`,
          margin: 0,
        }}
      >
        {/* Header */}
        <header
          className="slds-card__header slds-grid slds-grid_align-spread slds-grid_vertical-align-center"
          style={{ padding: '0.75rem 1rem' }}
        >
          <div className="slds-grid slds-grid_vertical-align-center" style={{ gap: '0.5rem' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '0.125rem 0.5rem',
                borderRadius: 3,
                background: badge.bg,
                color: badge.color,
                fontSize: '0.7rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
              }}
            >
              {badge.label}
            </span>
            {event.requires_dual_auth && (
              <span
                style={{
                  display: 'inline-block',
                  padding: '0.125rem 0.5rem',
                  borderRadius: 3,
                  background: '#fff4c7',
                  color: '#8a6d14',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  border: '1px solid #e49e00',
                }}
                title="This action exceeds a dual-auth threshold. A second senior compliance approver must sign off."
              >
                DUAL-AUTH
              </span>
            )}
            <h2
              id="hitl-panel-title"
              className="slds-text-heading_small"
              style={{ fontWeight: 600, marginLeft: '0.25rem' }}
            >
              Action Approval Required
            </h2>
          </div>
          <div
            style={{
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              color: expired ? '#c23934' : secondsRemaining < 60 ? '#ba4c1b' : '#16325c',
              fontWeight: 600,
            }}
            aria-label={`Expires in ${secondsRemaining} seconds`}
          >
            {expired ? 'EXPIRED' : `${formatCountdown(secondsRemaining)} left`}
          </div>
        </header>

        {/* Body */}
        <div className="slds-card__body slds-card__body_inner" style={{ padding: '0 1rem 1rem' }}>
          {/* Summary */}
          <p className="slds-text-body_regular slds-m-bottom_small" style={{ fontSize: '0.95rem' }}>
            {event.summary_text}
          </p>

          {/* Identifiers */}
          <div
            className="slds-grid slds-gutters_x-small slds-m-bottom_small"
            style={{ fontSize: '0.8rem' }}
          >
            <div className="slds-col">
              <span className="slds-text-color_weak">Client</span>
              <div style={{ fontFamily: 'monospace' }}>{event.client_id}</div>
            </div>
            <div className="slds-col">
              <span className="slds-text-color_weak">Account</span>
              <div style={{ fontFamily: 'monospace' }}>{event.account_id}</div>
            </div>
            <div className="slds-col">
              <span className="slds-text-color_weak">Plan hash</span>
              <div style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                {event.plan_hash.slice(0, 16)}…
              </div>
            </div>
          </div>

          {/* Plan details (collapsible JSON viewer) */}
          <details
            open={detailsOpen}
            onToggle={(e) => setDetailsOpen((e.target as HTMLDetailsElement).open)}
            style={{
              border: '1px solid #d8dde6',
              borderRadius: 4,
              marginBottom: '0.75rem',
              background: '#f4f6f9',
            }}
          >
            <summary
              style={{
                padding: '0.5rem 0.75rem',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#16325c',
              }}
            >
              Plan details ({Object.keys(event.plan_details || {}).length} fields)
            </summary>
            <pre
              style={{
                margin: 0,
                padding: '0.75rem',
                fontSize: '0.75rem',
                fontFamily: 'Menlo, Consolas, monospace',
                background: '#fff',
                borderTop: '1px solid #d8dde6',
                maxHeight: 240,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
              aria-label="Action plan details"
            >
              {JSON.stringify(event.plan_details ?? {}, null, 2)}
            </pre>
          </details>

          {/* Status banners */}
          {status === 'awaiting_second' && (
            <div
              className="slds-m-bottom_small"
              style={{
                background: '#fff4c7',
                padding: '0.75rem',
                borderLeft: '3px solid #e49e00',
                borderRadius: 2,
              }}
            >
              <strong>Waiting for second approver…</strong>
              <p className="slds-text-body_small slds-m-top_xx-small">
                Your approval was recorded. A senior compliance approver must sign off
                before the action executes.
              </p>
            </div>
          )}

          {status === 'approved' && (
            <div
              className="slds-m-bottom_small"
              style={{
                background: '#eef9f1',
                padding: '0.75rem',
                borderLeft: '3px solid #04844b',
                borderRadius: 2,
              }}
            >
              <strong>Submitted.</strong>
              {mulesoftReference && (
                <p className="slds-text-body_small slds-m-top_xx-small">
                  MuleSoft ref: <code>{mulesoftReference}</code>
                  {auditLogId && <> · Audit: <code>{auditLogId}</code></>}
                </p>
              )}
            </div>
          )}

          {status === 'rejected' && (
            <div
              className="slds-m-bottom_small"
              style={{
                background: '#fef1f1',
                padding: '0.75rem',
                borderLeft: '3px solid #c23934',
                borderRadius: 2,
              }}
            >
              <strong>Rejected.</strong>
              {reason && <p className="slds-text-body_small slds-m-top_xx-small">{reason}</p>}
            </div>
          )}

          {status === 'timed_out' && (
            <div
              className="slds-m-bottom_small"
              style={{
                background: '#fff4c7',
                padding: '0.75rem',
                borderLeft: '3px solid #e49e00',
                borderRadius: 2,
              }}
            >
              <strong>Timed out.</strong>
              <p className="slds-text-body_small slds-m-top_xx-small">
                The 5-minute approval window elapsed. The action was aborted. Re-run the
                request to generate a fresh approval.
              </p>
            </div>
          )}

          {status === 'error' && (
            <div
              className="slds-m-bottom_small"
              style={{
                background: '#fef1f1',
                padding: '0.75rem',
                borderLeft: '3px solid #c23934',
                borderRadius: 2,
              }}
            >
              <strong>Something went wrong.</strong>
              {reason && <p className="slds-text-body_small slds-m-top_xx-small">{reason}</p>}
            </div>
          )}

          {/* Approver note */}
          {!terminal && status === 'waiting_first' && (
            <div className="slds-form-element slds-m-bottom_small">
              <label
                className="slds-form-element__label slds-text-body_small"
                htmlFor="hitl-approver-note"
              >
                Approver note {mode === 'reject_note' && <span style={{ color: '#c23934' }}>(required)</span>}
              </label>
              <textarea
                id="hitl-approver-note"
                className="slds-textarea"
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value.slice(0, 500))}
                placeholder="Optional: explain the rationale. Written to IR_Audit_Log__c."
                disabled={submitting || expired}
              />
            </div>
          )}

          {/* Actions */}
          {!terminal && status === 'waiting_first' && mode === 'preview' && (
            <div className="slds-grid slds-grid_align-end" style={{ gap: '0.5rem' }}>
              <button
                type="button"
                className="slds-button slds-button_neutral"
                onClick={() => setMode('reject_note')}
                disabled={submitting || expired}
              >
                Reject
              </button>
              <button
                type="button"
                className="slds-button slds-button_brand"
                onClick={handleApprove}
                disabled={submitting || expired}
                autoFocus
              >
                {submitting ? 'Submitting…' : 'Approve'}
              </button>
            </div>
          )}

          {!terminal && status === 'waiting_first' && mode === 'reject_note' && (
            <div className="slds-grid slds-grid_align-end" style={{ gap: '0.5rem' }}>
              <button
                type="button"
                className="slds-button slds-button_neutral"
                onClick={() => setMode('preview')}
                disabled={submitting}
              >
                Back
              </button>
              <button
                type="button"
                className="slds-button slds-button_destructive"
                onClick={handleReject}
                disabled={submitting || !note.trim()}
              >
                {submitting ? 'Submitting…' : 'Confirm reject'}
              </button>
            </div>
          )}
        </div>

        {/* Footer — token hash prefix for forensic traceability */}
        <footer
          className="slds-card__footer"
          style={{
            padding: '0.5rem 1rem',
            background: '#f4f6f9',
            borderTop: '1px solid #d8dde6',
            fontFamily: 'monospace',
            fontSize: '0.7rem',
            color: '#706e6b',
          }}
        >
          token_hash: {event.token_hash.slice(0, 16)}…
        </footer>
      </div>
    </div>
  );
}

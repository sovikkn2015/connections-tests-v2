/**
 * Advisor Workbench v3 — Marcus Kerrigan's SLDS light surface.
 *
 * v3 over v2 (this iteration):
 *   - FSI Workforce 360 branding (PersonaHeaderV3 with Cognito sign-out)
 *   - TraversalMapV3 with map polish (tooltips, legend, this-turn filter)
 *   - Progressive-disclosure for gate chain — only renders when
 *     pendingPlan is set (approval in flight), avoiding the v2 problem
 *     where the advisor always showed 7 dim gates.
 *   - All conversation / queue / client-360 panels inherit from v2 so the
 *     v3 iteration stays focused on brand + map. Full redesign of those
 *     panels is roadmap for a later v3 minor.
 */

import { useRef, useState } from 'react';
import { PersonaHeaderV3 } from '../atoms/PersonaHeaderV3';
import { TraversalMapV3 } from '../atoms/TraversalMapV3';
import { EndToEndTrace } from '../../shared/components/EndToEndTrace';
import { GatesTrackerV2 } from '../../v2/atoms/GatesTrackerV2';
import { AuditStripV2 } from '../../v2/atoms/AuditStripV2';
import { InlineActionCard } from '../../v2/atoms/InlineActionCard';
import { StreamingText } from '../../shared/components/StreamingText';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useGateTracker } from '../../shared/hooks/useGateTracker';
import { useOptimisticApproval } from '../../shared/hooks/useOptimisticApproval';
import { useSessionStore } from '../../shared/store/session';
import { useBriefStore } from '../../shared/store/brief';
import type { ActionPlan } from '../../shared/types/api';
import type { OutboundMessage } from '../../shared/types/agent';

export interface AdvisorWorkbenchV3Props {
  onAuthExpired?: () => void;
  onOpenCitation?: (sourceId: string) => void;
  showSignOut?: boolean;
}

export function AdvisorWorkbenchV3({
  onAuthExpired,
  onOpenCitation,
  showSignOut = false,
}: AdvisorWorkbenchV3Props) {
  const [pendingPlan, setPendingPlan] = useState<ActionPlan | null>(null);
  const [query, setQuery] = useState('');
  const principalId = useSessionStore((s) => s.principalId) ?? 'anonymous';
  const gateTracker = useGateTracker();
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

  const sendRef = useRef<(m: OutboundMessage) => void>(() => {
    /* pre-socket */
  });
  const optimistic = useOptimisticApproval({
    send: (m) => sendRef.current(m),
    principalId,
  });

  const handleMessage = useStreamingTurn({
    onHitlPrompt: (ev) => {
      setPendingPlan(ev.plan);
      gateTracker.reset(ev.plan.plan_id);
    },
    onGate: gateTracker.handleGateEvent,
    onOptimisticConfirm: () => {
      optimistic.confirm();
      setPendingPlan(null);
    },
    onOptimisticRollback: optimistic.rollback,
  });

  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });
  sendRef.current = send;

  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const reset = useBriefStore((s) => s.reset);

  const submit = () => {
    if (!query.trim()) return;
    reset();
    send({ type: 'turn', turn_id: crypto.randomUUID(), text: query });
    setQuery('');
  };

  // Progressive disclosure: gate chain + tracker only when a plan is in flight
  const planInFlight = pendingPlan !== null;

  return (
    <ErrorBoundary>
      <div className="v3-advisor">
        <PersonaHeaderV3 persona="fsi_advisor" surface="light" showSignOut={showSignOut} />
        {planInFlight && <GatesTrackerV2 gates={gateTracker.gates} />}
        <div className="v3-advisor__body">
          <aside className="v3-advisor-col">
            <div className="v3-advisor-col__header">
              <span>Actions</span>
              <span style={{ fontSize: 10, color: 'var(--n-500)' }}>queue</span>
            </div>
            <div
              className="v3-advisor-col__body"
              style={{ padding: '1rem', color: 'var(--n-500)', fontSize: 13, fontStyle: 'italic' }}
            >
              Actions queue will populate as liaison hands off client inquiries.
              Details in V3.1.
            </div>
          </aside>

          <div className="v3-advisor-col">
            <div className="v3-advisor-col__header">
              <span>Conversation</span>
              <span className="fsi-mono" style={{ fontSize: 10, textTransform: 'none', letterSpacing: 0 }}>
                {pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④` : 'ready'}
              </span>
            </div>
            <div className="v3-advisor-col__body">
              <div style={{ padding: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(markdown || pendingPlan) && (
                  <div className="v3-msg">
                    <div className="v3-msg__avatar v3-msg__avatar--ai">FW</div>
                    <div className="v3-msg__body">
                      <div className="v3-msg__header">
                        <span className="v3-msg__name">FSI Workforce 360 · Advisor</span>
                        <span className="v3-msg__time">{isStreaming ? 'drafting…' : 'drafted'}</span>
                        <span className="v3-msg__tag">action_specialist</span>
                      </div>
                      {markdown && (
                        <div className="v3-msg__text">
                          <StreamingText
                            markdown={markdown}
                            citations={citations}
                            isStreaming={isStreaming}
                            onOpenCitation={onOpenCitation}
                          />
                        </div>
                      )}
                      {pendingPlan && (
                        <InlineActionCard
                          plan={pendingPlan}
                          state={optimistic.state}
                          onApprove={optimistic.approve}
                          onReject={optimistic.reject}
                          onEdit={() => {
                            optimistic.reset?.();
                            setPendingPlan(null);
                          }}
                        />
                      )}
                    </div>
                  </div>
                )}
                {!markdown && !pendingPlan && (
                  <div
                    style={{
                      color: 'var(--n-500)',
                      fontSize: 13,
                      fontStyle: 'italic',
                      padding: '1rem',
                      textAlign: 'center',
                    }}
                  >
                    Type a plan and press ⌘↵. Example: "Trim NVDA from 14.2% to 9.5% for Eleanor Vance".
                  </div>
                )}
              </div>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
              style={{
                padding: '0.5rem',
                borderTop: '1px solid var(--n-200)',
                display: 'flex',
                gap: '0.5rem',
                background: 'var(--n-025)',
              }}
            >
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Reply to the client or instruct the agent…  /research /draft /schedule"
                aria-label="Advisor query"
                rows={2}
                style={{
                  flex: 1,
                  padding: '0.375rem 0.5rem',
                  border: '1px solid var(--n-200)',
                  borderRadius: 'var(--radius-sm)',
                  fontFamily: 'inherit',
                  fontSize: '0.8125rem',
                  resize: 'vertical',
                }}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    submit();
                  }
                }}
              />
              <button type="submit" className="v3-btn-brand" style={{ alignSelf: 'stretch' }}>
                Send
              </button>
            </form>
          </div>

          <aside className="v3-advisor-col">
            <div className="v3-advisor-col__header">
              <span>Client 360</span>
              <span className="v3-live-dot" data-status="open">synced</span>
            </div>
            <div
              className="v3-advisor-col__body"
              style={{ padding: '1rem', color: 'var(--n-500)', fontSize: 13, fontStyle: 'italic' }}
            >
              Client 360 populates when an Actions item is selected. V3.1 brings
              the IPS allocation bar + concentration warnings.
            </div>
          </aside>
        </div>
        <details className="v3-map-panel" open>
          <summary>Architecture map — live traversal</summary>
          <TraversalMapV3
            fallbackPersona="fsi_advisor"
            gateChainVisible={planInFlight}
            langfuseBaseUrl={langfuseBaseUrl}
          />
        </details>
        <div className="v3-trace-panel">
          <EndToEndTrace langfuseBaseUrl={langfuseBaseUrl} />
        </div>
        <AuditStripV2 gates={gateTracker.gates} langfuseBaseUrl={langfuseBaseUrl} />
      </div>
    </ErrorBoundary>
  );
}

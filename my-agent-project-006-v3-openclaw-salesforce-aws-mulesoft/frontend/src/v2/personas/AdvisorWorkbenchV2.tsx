/**
 * Advisor Workbench v2 — Marcus Kerrigan's SLDS light surface.
 *
 * Big UX shift from v1: ActionCard is rendered INLINE in the conversation
 * as an AI message (not a modal). This matches the uploaded design's
 * "agent speaks the plan" framing.
 *
 * Real wiring:
 *   - WebSocket: useAgentSocket (existing)
 *   - Turn streaming: useStreamingTurn with onHitlPrompt capturing the plan
 *   - Gate tracker: useGateTracker (existing) — drives GatesTrackerV2
 *   - Optimistic approval: useOptimisticApproval (existing)
 *   - Queues: useQueuesStore (existing — fed by queue_update events)
 *   - Client context: fetched via rest.getSourceChunk when a queue item is
 *     selected; falls back to empty state.
 *
 * Narrative coverage:
 *   - N1 Earnings Morning: research → RM sees brief → draft trim plan (inline card)
 *   - N2 Client drives research: queue item appears in Actions tab from client handoff
 *   - N5 Large Liquidation: dual-auth required flag in InlineActionCard + MuleSoft gate
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import { PersonaHeaderV2 } from '../atoms/PersonaHeaderV2';
import { GatesTrackerV2 } from '../atoms/GatesTrackerV2';
import { TraversalMapV2 } from '../atoms/TraversalMapV2';
import { TimelineV2 } from '../atoms/TimelineV2';
import { AuditStripV2 } from '../atoms/AuditStripV2';
import { InlineActionCard } from '../atoms/InlineActionCard';
import { StreamingText } from '../../shared/components/StreamingText';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useGateTracker } from '../../shared/hooks/useGateTracker';
import { useOptimisticApproval } from '../../shared/hooks/useOptimisticApproval';
import { useQueuesStore } from '../../shared/store/queues';
import { useSessionStore } from '../../shared/store/session';
import { useBriefStore } from '../../shared/store/brief';
import type { ActionPlan, AdvisorQueueKind, QueueItemSummary } from '../../shared/types/api';
import type { OutboundMessage } from '../../shared/types/agent';

/* ------------------------------------------------------------------ */
/* Queues column                                                        */
/* ------------------------------------------------------------------ */

const TAB_ORDER: Array<{ kind: AdvisorQueueKind; label: string }> = [
  { kind: 'alerts', label: 'Actions' },
  { kind: 'briefs', label: 'Insights' },
  { kind: 'inbox', label: 'Tasks' },
];

function priorityFromBadge(badge?: string): 'high' | 'med' | 'low' {
  if (!badge) return 'med';
  const b = badge.toLowerCase();
  if (b.includes('high') || b.includes('urgent')) return 'high';
  if (b.includes('low')) return 'low';
  return 'med';
}

function formatRelative(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const diff = Date.now() - t;
  if (diff < 60_000) return 'now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return new Date(t).toLocaleDateString();
}

function QueuesColumn() {
  const [activeTab, setActiveTab] = useState<AdvisorQueueKind>('alerts');
  const items = useQueuesStore((s) => s.itemsByQueue[activeTab]);
  const counts = useQueuesStore((s) => ({
    alerts: s.itemsByQueue.alerts.length,
    briefs: s.itemsByQueue.briefs.length,
    inbox: s.itemsByQueue.inbox.length,
  }));
  const selectItem = useQueuesStore((s) => s.selectItem);
  const selectedItemId = useQueuesStore((s) => s.selectedItemId);

  return (
    <aside className="v2-advisor-col">
      <div className="v2-queue-tabs" role="tablist">
        {TAB_ORDER.map((t) => (
          <button
            key={t.kind}
            type="button"
            role="tab"
            className="v2-queue-tab"
            aria-selected={activeTab === t.kind}
            onClick={() => setActiveTab(t.kind)}
          >
            {t.label}
            <span className="v2-queue-tab__count">{counts[t.kind as 'alerts' | 'briefs' | 'inbox']}</span>
          </button>
        ))}
      </div>
      <div className="v2-advisor-col__body">
        {items.length === 0 ? (
          <div
            style={{
              padding: '1rem 0.75rem',
              color: 'var(--n-500)',
              fontSize: '0.75rem',
              fontStyle: 'italic',
            }}
          >
            No items in {TAB_ORDER.find((t) => t.kind === activeTab)?.label.toLowerCase()} yet.
          </div>
        ) : (
          items.map((it) => {
            const prio = priorityFromBadge(it.badge);
            return (
              <div
                key={it.id}
                className="v2-queue-item"
                data-unread={it.unread}
                data-selected={it.id === selectedItemId}
                role="button"
                tabIndex={0}
                onClick={() => selectItem(it.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectItem(it.id);
                  }
                }}
              >
                <div className="v2-queue-item__title">
                  <span>{it.title}</span>
                </div>
                {it.subtitle && <div className="v2-queue-item__subtitle">{it.subtitle}</div>}
                <div className="v2-queue-item__meta">
                  <span className={`v2-queue-item__priority v2-queue-item__priority--${prio}`}>
                    {prio}
                  </span>
                  <span className="w360-mono">{formatRelative(it.timestamp)}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Conversation column — inline AI message + inline ActionCard         */
/* ------------------------------------------------------------------ */

interface ConversationMessage {
  id: string;
  kind: 'client' | 'user' | 'ai';
  name: string;
  time: string;
  tag?: string;
  text?: string;
  /** Attach the action card inside this message */
  attachedPlan?: ActionPlan;
}

function ConversationColumn({
  send,
  pendingPlan,
  approval,
  onClearPending,
  onOpenCitation,
}: {
  send: (m: OutboundMessage) => void;
  pendingPlan: ActionPlan | null;
  approval: ReturnType<typeof useOptimisticApproval>;
  onClearPending: () => void;
  onOpenCitation?: (sourceId: string) => void;
}) {
  const [query, setQuery] = useState('');
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const reset = useBriefStore((s) => s.reset);

  // Persisted conversation messages (additional to the live brief stream).
  // History is in-memory only for now; persisted messages come from CRM via
  // rest.getClientContact() in a later iteration.
  const [messages] = useState<ConversationMessage[]>([]);

  const submit = useCallback(() => {
    if (!query.trim()) return;
    reset();
    send({ type: 'turn', turn_id: crypto.randomUUID(), text: query });
    setQuery('');
  }, [query, reset, send]);

  return (
    <div className="v2-advisor-col">
      <div className="v2-advisor-col__header">
        <span>Conversation</span>
        <span className="w360-mono" style={{ fontSize: 10, textTransform: 'none', letterSpacing: 0 }}>
          {pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④` : 'ready'}
        </span>
      </div>
      <div className="v2-advisor-col__body">
        <div className="v2-conversation">
          {messages.map((m) => (
            <div key={m.id} className="v2-msg">
              <div
                className={`v2-msg__avatar v2-msg__avatar--${
                  m.kind === 'client' ? 'client' : m.kind === 'user' ? 'user' : 'ai'
                }`}
              >
                {m.name
                  .split(' ')
                  .map((p) => p[0])
                  .slice(0, 2)
                  .join('')}
              </div>
              <div className="v2-msg__body">
                <div className="v2-msg__header">
                  <span className="v2-msg__name">{m.name}</span>
                  <span className="v2-msg__time">{m.time}</span>
                  {m.tag && <span className="v2-msg__tag">{m.tag}</span>}
                </div>
                {m.text && <div className="v2-msg__text">{m.text}</div>}
                {m.attachedPlan && (
                  <InlineActionCard
                    plan={m.attachedPlan}
                    state={approval.state}
                    onApprove={approval.approve}
                    onReject={approval.reject}
                  />
                )}
              </div>
            </div>
          ))}

          {/* Live AI brief + optional inline ActionCard */}
          {(markdown || pendingPlan) && (
            <div className="v2-msg">
              <div className="v2-msg__avatar v2-msg__avatar--ai" aria-hidden="true">
                W3
              </div>
              <div className="v2-msg__body">
                <div className="v2-msg__header">
                  <span className="v2-msg__name">Workflow 360 · Advisor</span>
                  <span className="v2-msg__time">
                    {isStreaming ? 'drafting…' : 'drafted'}
                  </span>
                  <span className="v2-msg__tag">action_specialist</span>
                </div>
                {markdown && (
                  <div className="v2-msg__text">
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
                    state={approval.state}
                    onApprove={approval.approve}
                    onReject={approval.reject}
                    onEdit={() => {
                      // Clear the pending plan so the RM can re-type with
                      // modifications. The draft turn was a single Bedrock
                      // call — no server-side state to roll back.
                      approval.reset?.();
                      onClearPending();
                    }}
                  />
                )}
              </div>
            </div>
          )}

          {/* Empty state when no turn has run */}
          {!markdown && !pendingPlan && messages.length === 0 && (
            <div
              style={{
                color: 'var(--n-500)',
                fontSize: '0.875rem',
                fontStyle: 'italic',
                padding: '1rem',
                textAlign: 'center',
              }}
            >
              Ask the platform. Try: <span className="w360-mono">/research NVDA</span>,{' '}
              <span className="w360-mono">/trim above-IPS-ceiling</span>, or type a question.
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
        <button type="submit" className="btn-brand" style={{ alignSelf: 'stretch' }}>
          Send
        </button>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Client 360 column                                                    */
/* ------------------------------------------------------------------ */

function ClientContextColumn({ selectedItem }: { selectedItem: QueueItemSummary | null }) {
  // When a queue item is selected, the client id is known — fetch household.
  // Here we render either the selection's brief context or a placeholder.
  return (
    <aside className="v2-advisor-col">
      <div className="v2-advisor-col__header">
        <span>Client 360</span>
        <span className="live-dot" data-status="open">synced</span>
      </div>
      <div className="v2-advisor-col__body v2-client-context">
        {!selectedItem ? (
          <div
            style={{
              padding: '1rem',
              color: 'var(--n-500)',
              fontSize: '0.8125rem',
              fontStyle: 'italic',
            }}
          >
            Select an item from the Actions queue to load the client's household.
          </div>
        ) : (
          <>
            <div className="v2-client-context__head">
              <div className="v2-client-context__avatar">
                {selectedItem.title.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="v2-client-context__name">{selectedItem.title}</div>
                <div className="v2-client-context__sub">
                  {selectedItem.client_contact_id ?? '—'}
                </div>
              </div>
            </div>
            <div className="v2-client-context__section">
              <div className="v2-client-context__section-title">Context</div>
              <div className="v2-client-context__row">
                <span className="v2-client-context__row-label">Source queue</span>
                <span className="v2-client-context__row-value">{selectedItem.kind}</span>
              </div>
              {selectedItem.subtitle && (
                <div className="v2-client-context__row">
                  <span className="v2-client-context__row-label">Detail</span>
                  <span
                    className="v2-client-context__row-value"
                    style={{ fontSize: 10, textAlign: 'right' }}
                  >
                    {selectedItem.subtitle}
                  </span>
                </div>
              )}
            </div>
            <div className="v2-client-context__section">
              <div className="v2-client-context__section-title">Recent signals</div>
              <div className="v2-signal">
                <div className="v2-signal__icon">⚑</div>
                <div>
                  <div className="v2-signal__title">{selectedItem.badge ?? 'Flagged'}</div>
                  <div className="v2-signal__desc">{formatRelative(selectedItem.timestamp)}</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Root                                                                 */
/* ------------------------------------------------------------------ */

export interface AdvisorWorkbenchV2Props {
  onAuthExpired?: () => void;
  onOpenCitation?: (sourceId: string) => void;
}

export function AdvisorWorkbenchV2({
  onAuthExpired,
  onOpenCitation,
}: AdvisorWorkbenchV2Props) {
  const [pendingPlan, setPendingPlan] = useState<ActionPlan | null>(null);
  const principalId = useSessionStore((s) => s.principalId) ?? 'anonymous';
  const gateTracker = useGateTracker();
  const removeQueueItem = useQueuesStore((s) => s.removeItem);
  const selectedItemId = useQueuesStore((s) => s.selectedItemId);
  const allItems = useQueuesStore((s) => s.itemsByQueue);
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
    onQueueUpdate: (ev) => {
      if (ev.op === 'remove') {
        removeQueueItem(ev.queue, ev.item_id);
      }
    },
  });

  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });
  sendRef.current = send;

  const selectedItem = useMemo(() => {
    if (!selectedItemId) return null;
    for (const kind of Object.keys(allItems) as AdvisorQueueKind[]) {
      const hit = allItems[kind].find((i) => i.id === selectedItemId);
      if (hit) return hit;
    }
    return null;
  }, [selectedItemId, allItems]);

  return (
    <ErrorBoundary>
      <div className="v2-advisor">
        <PersonaHeaderV2 persona="fsi_advisor" surface="light" />
        <GatesTrackerV2 gates={gateTracker.gates} />
        <div className="v2-advisor__body">
          <QueuesColumn />
          <ConversationColumn
            send={send}
            pendingPlan={pendingPlan}
            approval={optimistic}
            onClearPending={() => setPendingPlan(null)}
            onOpenCitation={onOpenCitation}
          />
          <ClientContextColumn selectedItem={selectedItem} />
        </div>
        <details className="v2-map-panel" open>
          <summary>Trust spine — live</summary>
          <TraversalMapV2
            fallbackPersona="fsi_advisor"
            showGates
            langfuseBaseUrl={langfuseBaseUrl}
          />
          <TimelineV2
            persona="fsi_advisor"
            gates={gateTracker.gates}
            langfuseBaseUrl={langfuseBaseUrl}
          />
        </details>
        <AuditStripV2 gates={gateTracker.gates} langfuseBaseUrl={langfuseBaseUrl} />
      </div>
    </ErrorBoundary>
  );
}

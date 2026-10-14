/**
 * Advisor Workbench V4 — Marcus Kerrigan's SLDS-light console.
 *
 * Pixel-honest port of the uploaded design (UIUX Design/advisor.jsx):
 *  - 44px header · 7-gate tracker · 3-column body (280 / 1fr / 380) ·
 *    trust spine · audit strip
 *  - Column 1 Queues: Actions / Insights / Tasks tabs with live count badges
 *    and priority chips (high/med/low) driven by `useQueuesStore.itemsByQueue`
 *  - Column 2 Conversation: client + RM turns in avatar bubbles, inline
 *    action-card when a hitl_prompt arrives
 *  - Column 3 Client 360: holdings overview + IPS allocation bar +
 *    concentration warnings
 *
 * Backend wiring is unchanged from v3 — same useAgentSocket,
 * useStreamingTurn, useGateTracker, useOptimisticApproval flow. Only the
 * visual skin is rebuilt.
 */

import { useMemo, useRef, useState } from 'react';
import { PersonaHeaderV4 } from '../atoms/PersonaHeaderV4';
import { GatesTrackerV4 } from '../atoms/GatesTrackerV4';
import { TrustSpineV4 } from '../atoms/TrustSpineV4';
import { AuditStripV4 } from '../atoms/AuditStripV4';
import { InlineActionCardV4 } from '../atoms/InlineActionCardV4';
import { StreamingText } from '../../shared/components/StreamingText';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useGateTracker } from '../../shared/hooks/useGateTracker';
import { useOptimisticApproval } from '../../shared/hooks/useOptimisticApproval';
import { useSessionStore } from '../../shared/store/session';
import { useBriefStore } from '../../shared/store/brief';
import { useQueuesStore } from '../../shared/store/queues';
import type { AdvisorQueueKind, ActionPlan, QueueItemSummary } from '../../shared/types/api';
import type { OutboundMessage } from '../../shared/types/agent';

const QUEUE_TABS: Array<{ id: AdvisorQueueKind; label: string }> = [
  { id: 'alerts', label: 'Actions' },
  { id: 'briefs', label: 'Insights' },
  { id: 'pending', label: 'Tasks' },
];

function priorityFor(item: QueueItemSummary): 'high' | 'med' | 'low' {
  if (!item.badge) return 'low';
  const b = item.badge.toLowerCase();
  if (b.includes('high') || b.includes('urgent') || b.includes('!')) return 'high';
  if (b.includes('med') || b.includes('priority')) return 'med';
  return 'low';
}

function formatHM(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (!Number.isFinite(d.getTime())) return '—';
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return '—';
  }
}

function QueuesPanel({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const byQueue = useQueuesStore((s) => s.itemsByQueue);
  const [activeTab, setActiveTab] = useState<AdvisorQueueKind>('alerts');
  const items = byQueue[activeTab] ?? [];
  const counts = {
    alerts: (byQueue.alerts ?? []).length,
    briefs: (byQueue.briefs ?? []).length,
    pending: (byQueue.pending ?? []).length,
    inbox: (byQueue.inbox ?? []).length,
  };

  return (
    <aside className="advisor-col" aria-label="Queues">
      <div className="queue-tabs" role="tablist">
        {QUEUE_TABS.map((q) => (
          <button
            key={q.id}
            className="queue-tab"
            role="tab"
            aria-selected={activeTab === q.id}
            onClick={() => setActiveTab(q.id)}
            type="button"
          >
            {q.label}
            <span className="queue-tab__count">{counts[q.id]}</span>
          </button>
        ))}
      </div>
      <div className="advisor-col__body">
        {items.length === 0 ? (
          <div style={{ padding: 14, color: 'var(--v4-n-500)', fontSize: 12, fontStyle: 'italic' }}>
            Empty — items arrive via queue_update events from the liaison and research orchestrators.
          </div>
        ) : (
          items.map((it) => {
            const priority = priorityFor(it);
            return (
              <button
                key={it.id}
                type="button"
                className="queue-item"
                data-unread={it.unread || undefined}
                data-selected={it.id === selectedId || undefined}
                onClick={() => onSelect(it.id)}
              >
                <div className="queue-item__title">
                  <span>{it.title}</span>
                </div>
                {it.subtitle && <div className="queue-item__subtitle">{it.subtitle}</div>}
                <div className="queue-item__meta">
                  <span className={`queue-item__priority queue-item__priority--${priority}`}>
                    {priority}
                  </span>
                  <span className="w360-mono">{formatHM(it.timestamp)}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}

interface ConversationPanelProps {
  pendingPlan: ActionPlan | null;
  approvalState: ReturnType<typeof useOptimisticApproval>['state'];
  onApprove: (planId: string, planHash: string) => void;
  onReject: (planId: string, planHash: string) => void;
  onEditPlan: () => void;
  query: string;
  onQueryChange: (v: string) => void;
  onSubmit: () => void;
}

function ConversationPanel({
  pendingPlan,
  approvalState,
  onApprove,
  onReject,
  onEditPlan,
  query,
  onQueryChange,
  onSubmit,
}: ConversationPanelProps) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);

  return (
    <div className="advisor-col" aria-label="Conversation">
      <div className="advisor-col__header">
        <span>Conversation</span>
        <span
          className="w360-mono"
          style={{ fontSize: 10, color: 'var(--v4-n-500)', textTransform: 'none', letterSpacing: 0, fontWeight: 500 }}
        >
          {pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④` : 'ready'}
        </span>
      </div>
      <div className="advisor-col__body">
        <div className="conversation">
          {(markdown || pendingPlan) && (
            <div className="msg">
              <div className="msg__avatar msg__avatar--ai">AI</div>
              <div className="msg__body">
                <div className="msg__header">
                  <span className="msg__name">FSI Workforce 360 · Advisor</span>
                  <span className="msg__time">
                    {isStreaming ? 'drafting…' : pendingPlan ? 'drafted' : 'done'}
                  </span>
                  {pendingPlan && <span className="msg__tag">action_specialist</span>}
                </div>
                {markdown && (
                  <div className="msg__text">
                    <StreamingText
                      markdown={markdown}
                      citations={citations}
                      isStreaming={isStreaming}
                      onOpenCitation={() => {
                        /* citation drill-down follows v5 */
                      }}
                    />
                  </div>
                )}
                {pendingPlan && (
                  <InlineActionCardV4
                    plan={pendingPlan}
                    state={approvalState}
                    onApprove={onApprove}
                    onReject={onReject}
                    onEdit={onEditPlan}
                  />
                )}
              </div>
            </div>
          )}
          {!markdown && !pendingPlan && (
            <div
              style={{
                color: 'var(--v4-n-500)',
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
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <textarea
          placeholder="Reply to the client or instruct the agent…  /research /draft /schedule"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
              e.preventDefault();
              onSubmit();
            }
          }}
          aria-label="Advisor composer"
        />
        <button type="submit" className="btn-brand" style={{ height: 36 }}>
          Send
        </button>
      </form>
    </div>
  );
}

function ClientContextPanel({ selectedItem }: { selectedItem: QueueItemSummary | null }) {
  return (
    <aside className="advisor-col client-context" aria-label="Client 360">
      <div className="advisor-col__header">
        <span>Client 360{selectedItem ? ` · ${selectedItem.title.slice(0, 30)}` : ''}</span>
        <span
          style={{ fontSize: 10, color: 'var(--v4-success-500)', textTransform: 'none', letterSpacing: 0 }}
        >
          ● synced
        </span>
      </div>
      <div className="advisor-col__body">
        {!selectedItem ? (
          <div style={{ padding: 14, color: 'var(--v4-n-500)', fontSize: 12, fontStyle: 'italic' }}>
            Select an item in the Actions queue to see client context. Holdings, IPS allocation,
            and concentration signals render here.
          </div>
        ) : (
          <>
            <div className="client-context__head">
              <div className="client-context__avatar">
                {selectedItem.title
                  .split(/[\s·]+/)
                  .slice(0, 2)
                  .map((w) => w[0])
                  .filter(Boolean)
                  .join('')
                  .slice(0, 2)
                  .toUpperCase() || 'CL'}
              </div>
              <div>
                <div className="client-context__name">{selectedItem.title}</div>
                <div className="client-context__sub">{selectedItem.subtitle ?? 'Client · Wealth'}</div>
              </div>
            </div>
            <div className="client-context__section">
              <div className="client-context__section-title">Holdings overview</div>
              <div className="client-context__row">
                <span className="client-context__row-label">Total AUM</span>
                <span className="client-context__row-value">—</span>
              </div>
              <div className="client-context__row">
                <span className="client-context__row-label">Cash sleeve</span>
                <span className="client-context__row-value">—</span>
              </div>
              <div style={{ padding: '8px 0 0', color: 'var(--v4-n-500)', fontSize: 11, fontStyle: 'italic' }}>
                Holdings populate when the CRM MCP call for this household returns. V4 wiring runs on
                row-select; live payload in v5.
              </div>
            </div>
            <div className="client-context__section">
              <div className="client-context__section-title">Allocation vs. IPS</div>
              <div className="client-context__alloc">
                <div className="client-context__alloc-seg" style={{ width: '62%', background: 'var(--v4-brand-500)' }} />
                <div className="client-context__alloc-seg" style={{ width: '22%', background: 'var(--v4-trust-skill)' }} />
                <div className="client-context__alloc-seg" style={{ width: '9%', background: 'var(--v4-trust-mcp)' }} />
                <div className="client-context__alloc-seg" style={{ width: '4%', background: 'var(--v4-trust-gate)' }} />
                <div className="client-context__alloc-seg" style={{ width: '3%', background: 'var(--v4-n-500)' }} />
              </div>
              <div className="client-context__alloc-key">
                <div className="client-context__alloc-key-item">
                  <span className="client-context__alloc-key-dot" style={{ background: 'var(--v4-brand-500)' }} />
                  Equity 62%
                </div>
                <div className="client-context__alloc-key-item">
                  <span className="client-context__alloc-key-dot" style={{ background: 'var(--v4-trust-skill)' }} />
                  Fixed 22%
                </div>
                <div className="client-context__alloc-key-item">
                  <span className="client-context__alloc-key-dot" style={{ background: 'var(--v4-trust-mcp)' }} />
                  Alts 9%
                </div>
                <div className="client-context__alloc-key-item">
                  <span className="client-context__alloc-key-dot" style={{ background: 'var(--v4-trust-gate)' }} />
                  RE 4%
                </div>
              </div>
            </div>
            <div className="client-context__section">
              <div className="client-context__section-title">Recent signals</div>
              <div className="signal">
                <div className="signal__icon">⚑</div>
                <div>
                  <div className="signal__title">Awaiting live data</div>
                  <div className="signal__desc">
                    Signals populate from CRM + compliance_sweep skill when the household id is resolved.
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

export interface AdvisorWorkbenchV4Props {
  onAuthExpired?: () => void;
}

export function AdvisorWorkbenchV4({ onAuthExpired }: AdvisorWorkbenchV4Props) {
  const [pendingPlan, setPendingPlan] = useState<ActionPlan | null>(null);
  const [query, setQuery] = useState('');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const principalId = useSessionStore((s) => s.principalId) ?? 'anonymous';
  const gateTracker = useGateTracker();
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

  const sendRef = useRef<(m: OutboundMessage) => void>(() => {});
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
    // Wire backend queue_update events into the queue store so Actions /
    // Insights / Tasks tabs populate in real time. The transport now
    // forwards the full item payload on add/update (earlier it was
    // dropped — see shared/lib/httpAgentTransport.ts fix). 'remove'
    // evicts by id.
    onQueueUpdate: (ev) => {
      const queues = useQueuesStore.getState();
      if (ev.op === 'remove') {
        queues.removeItem(ev.queue, ev.item_id);
        return;
      }
      if (ev.item) {
        // Defensive: the item's declared kind must match the event queue.
        // The backend always sets both, but if they drift we trust the
        // outer event (queue) so the item lands in the expected tab.
        queues.upsertItem({ ...ev.item, kind: ev.queue });
      }
    },
  });

  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });
  sendRef.current = send;
  const reset = useBriefStore((s) => s.reset);

  const submit = () => {
    if (!query.trim()) return;
    reset();
    send({ type: 'turn', turn_id: crypto.randomUUID(), text: query });
    setQuery('');
  };

  const planInFlight = pendingPlan !== null;

  const byQueue = useQueuesStore((s) => s.itemsByQueue);
  const selectedItem = useMemo(() => {
    if (!selectedItemId) return null;
    const all = [
      ...(byQueue.alerts ?? []),
      ...(byQueue.briefs ?? []),
      ...(byQueue.pending ?? []),
      ...(byQueue.inbox ?? []),
    ];
    return all.find((it) => it.id === selectedItemId) ?? null;
  }, [byQueue, selectedItemId]);

  return (
    <ErrorBoundary>
      <div className="advisor-root" data-testid="v4-advisor">
        <PersonaHeaderV4 persona="fsi_advisor" />
        {planInFlight && <GatesTrackerV4 gates={gateTracker.gates} />}
        <div className="advisor-body">
          <QueuesPanel selectedId={selectedItemId} onSelect={setSelectedItemId} />
          <ConversationPanel
            pendingPlan={pendingPlan}
            approvalState={optimistic.state}
            onApprove={optimistic.approve}
            onReject={optimistic.reject}
            onEditPlan={() => {
              optimistic.reset?.();
              setPendingPlan(null);
            }}
            query={query}
            onQueryChange={setQuery}
            onSubmit={submit}
          />
          <ClientContextPanel selectedItem={selectedItem} />
        </div>
        <TrustSpineV4
          persona="fsi_advisor"
          eyebrowLeft={
            <>
              <strong>Trust spine</strong> · same orchestrator graph as Sarah's research, now lit
              through advisor_orch
            </>
          }
          eyebrowRight={pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④ HITL` : ''}
          gates={gateTracker.gates}
          langfuseBaseUrl={langfuseBaseUrl}
        />
        <AuditStripV4 />
      </div>
    </ErrorBoundary>
  );
}

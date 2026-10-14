/**
 * Advisor Workbench V6 — Marcus Kerrigan's SLDS-light console.
 *
 * Layout: header → gates tracker (when pending plan) → 3-column body
 * (queues 280px | conversation 1fr | client360 380px) → collapsible
 * trust spine → audit strip.
 *
 * Imports V4 atoms for gates tracker, inline action card, trust spine
 * components, and audit strip.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PersonaHeaderV6 } from '../atoms/PersonaHeaderV6';
import { SampleQueries } from '../atoms/SampleQueries';
import type { QueryCategory } from '../atoms/SampleQueries';
import { GatesTrackerV4 } from '../../v4/atoms/GatesTrackerV4';
import { TraversalMapV4 } from '../../v4/atoms/TraversalMapV4';
import { TimelineV4 } from '../../v4/atoms/TimelineV4';
import { AuditStripV4 } from '../../v4/atoms/AuditStripV4';
import { InlineActionCardV4 } from '../../v4/atoms/InlineActionCardV4';
import { StreamingText } from '../../shared/components/StreamingText';
import { VoiceButton } from '../../shared/components/VoiceButton';
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

/* ── Sample queries ─────────────────────────────────────────────────── */

const ADVISOR_QUERIES: QueryCategory[] = [
  {
    label: 'Trade orders',
    queries: [
      { text: 'Trim Patel META from 6.8% to 4.5% of equity sleeve', narrative: true, hint: '7 gates fire serially. LLM cannot skip a gate. Without OpenClaw: gates would be prompt-advisory.' },
      { text: 'Trim NVDA from 14.2% to 9.5% for Eleanor Vance', narrative: true, hint: 'Triggers action_specialist → 7-gate write path → HITL approval' },
      { text: 'Buy 500 shares of MSFT for the Chen household', hint: 'Suitability check + IPS policy validation before order draft' },
    ],
  },
  {
    label: 'Wire transfers',
    queries: [
      { text: 'Initiate a $50,000 wire from Patel account to external bank', hint: 'MuleSoft gate routes to Dwolla sandbox. Dual-auth required above $100K.' },
    ],
  },
  {
    label: 'Portfolio review',
    queries: [
      { text: 'Show me the Patel household concentration report', hint: 'portfolio_specialist pulls from CRM + runs concentration analysis' },
      { text: 'What is Eleanor Vance current allocation vs IPS?', hint: 'IPS policy band check with visual allocation bar' },
    ],
  },
  {
    label: 'Suitability',
    queries: [
      { text: 'Run suitability check on a 10% NVDA position for Nakamura', hint: 'Deterministic PASS/FAIL/REVIEW — not LLM math' },
      { text: 'Is a concentrated tech position suitable for the Al-Rashid household?', hint: 'Cross-references IPS constraints with current holdings' },
    ],
  },
  {
    label: 'Research awareness',
    queries: [
      { text: 'What did Sarah publish on NVDA this week?', hint: 'research_awareness skill queries Research_Brief__c in Salesforce' },
      { text: 'Any new research briefs relevant to the Patel portfolio?', hint: 'Cross-references client holdings with published briefs' },
    ],
  },
  {
    label: 'General',
    queries: [
      { text: 'Schedule a call with Eleanor Vance for Thursday 2pm', hint: 'Calendar integration (placeholder — not wired to real calendar)' },
      { text: 'Draft a follow-up email to the Patel family about the META trim', hint: 'Uses conversation context + action history' },
    ],
  },
];

/* ── Queue tabs config ──────────────────────────────────────────────── */

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

/* ── Queues panel ───────────────────────────────────────────────────── */

function QueuesPanel({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
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
    <aside className="slds-card" aria-label="Queues">
      <div className="slds-card__header">
        <span>Queues</span>
        <span className="slds-card__status slds-card__status--idle" style={{ textTransform: 'none', letterSpacing: 0 }}>
          {counts.alerts + counts.briefs + counts.pending} items
        </span>
      </div>
      <div className="v6-queue-tabs" role="tablist">
        {QUEUE_TABS.map((q) => (
          <button
            key={q.id}
            className="v6-queue-tab"
            role="tab"
            aria-selected={activeTab === q.id}
            onClick={() => setActiveTab(q.id)}
            type="button"
          >
            {q.label}
            <span className="v6-queue-tab__count">{counts[q.id]}</span>
          </button>
        ))}
      </div>
      <div>
        {items.length === 0 ? (
          <div className="slds-card__body">
            <div className="slds-card__empty">
              Empty — items arrive via queue_update events from the liaison and research
              orchestrators.
            </div>
          </div>
        ) : (
          items.map((it) => {
            const priority = priorityFor(it);
            return (
              <button
                key={it.id}
                type="button"
                className="v6-queue-item"
                data-unread={it.unread || undefined}
                data-selected={it.id === selectedId || undefined}
                onClick={() => onSelect(it.id)}
              >
                <div className="v6-queue-item__title">{it.title}</div>
                {it.subtitle && <div className="v6-queue-item__subtitle">{it.subtitle}</div>}
                <div className="v6-queue-item__meta">
                  <span className={`v6-queue-item__priority v6-queue-item__priority--${priority}`}>
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

/* ── Conversation panel ─────────────────────────────────────────────── */

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
    <div className="slds-card" aria-label="Conversation">
      <div className="slds-card__header">
        <span>Conversation</span>
        <span className="slds-card__status slds-card__status--idle" style={{ textTransform: 'none', letterSpacing: 0 }}>
          {pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④` : 'ready'}
        </span>
      </div>
      <div className="slds-card__body" style={{ minHeight: 300 }}>
        <div className="v6-conversation">
          {(markdown || pendingPlan) && (
            <div className="v6-msg">
              <div className="v6-msg__avatar">AI</div>
              <div className="v6-msg__body">
                <div className="v6-msg__header">
                  <span className="v6-msg__name">FSI Workforce 360 · Advisor</span>
                  <span className="v6-msg__time">
                    {isStreaming ? 'drafting…' : pendingPlan ? 'drafted' : 'done'}
                  </span>
                  {pendingPlan && <span className="v6-msg__tag">action_specialist</span>}
                </div>
                {markdown && (
                  <div className="v6-msg__text">
                    <StreamingText
                      markdown={markdown}
                      citations={citations}
                      isStreaming={isStreaming}
                      onOpenCitation={() => {}}
                    />
                  </div>
                )}
                {pendingPlan && (
                  <div className="v4-root">
                    <InlineActionCardV4
                      plan={pendingPlan}
                      state={approvalState}
                      onApprove={onApprove}
                      onReject={onReject}
                      onEdit={onEditPlan}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
          {!markdown && !pendingPlan && (
            <div className="slds-card__empty" style={{ textAlign: 'center', padding: '1rem' }}>
              Type a plan and press ⌘↵. Example: "Trim NVDA from 14.2% to 9.5% for Eleanor Vance".
            </div>
          )}
        </div>
      </div>
      <form
        className="v6-composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <VoiceButton
          onTranscript={onQueryChange}
          onFinal={(text) => { onQueryChange(text); }}
          className="v6-btn v6-btn--ghost"
          style={{ height: 36, width: 36, padding: 0, fontSize: 16 }}
        />
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
        <button type="submit" className="v6-btn v6-btn--brand" style={{ height: 36 }}>
          Send
        </button>
      </form>
    </div>
  );
}

/* ── Client 360 types & helpers ──────────────────────────────────────── */

/** Position returned by the salesforce-crm `read_household_summary` tool. */
interface HouseholdPosition {
  ticker: string;
  pct_of_portfolio: number;
  asset_class: string;
}

/** Shape returned by `POST /mcp/salesforce-crm/tools/call` for `read_household_summary`. */
interface HouseholdSummary {
  household_id: string;
  household_name: string;
  primary_contact_id?: string;
  positions: HouseholdPosition[];
  recent_changes_pct?: Array<{ ticker: string; change_pct_30d: number }>;
  next_events?: string[];
  open_items?: string[];
  last_contact_at?: string;
  family_events?: string[];
  dataSource?: string;
}

type Client360FetchStatus = 'idle' | 'loading' | 'loaded' | 'error';

/** Allocation bucket for the IPS bar. */
interface AllocBucket {
  label: string;
  pct: number;
  color: string;
}

const ASSET_CLASS_META: Record<string, { label: string; color: string }> = {
  equity:  { label: 'Equity', color: 'var(--v6-brand)' },
  fixed:   { label: 'Fixed',  color: 'var(--v6-success)' },
  alts:    { label: 'Alts',   color: '#8b5cf6' },
  re:      { label: 'RE',     color: 'var(--v6-warning)' },
  cash:    { label: 'Cash',   color: 'var(--v6-text-secondary)' },
};

/** Aggregate positions by asset_class into allocation buckets. */
function buildAllocation(positions: HouseholdPosition[]): AllocBucket[] {
  const totals = new Map<string, number>();
  for (const p of positions) {
    const cls = p.asset_class.toLowerCase();
    totals.set(cls, (totals.get(cls) ?? 0) + p.pct_of_portfolio);
  }
  const buckets: AllocBucket[] = [];
  for (const [cls, pct] of totals) {
    const meta = ASSET_CLASS_META[cls] ?? { label: cls, color: 'var(--v6-text-secondary)' };
    buckets.push({ label: meta.label, pct: Math.round(pct * 10) / 10, color: meta.color });
  }
  // Sort descending by pct so the bar reads large → small.
  buckets.sort((a, b) => b.pct - a.pct);
  return buckets;
}

/** Format a dollar amount into a compact AUM string (e.g. "$4.2M"). */
function formatAum(positions: HouseholdPosition[]): string {
  // The MCP returns pct_of_portfolio, not dollar amounts. We can't derive
  // a real AUM without a total-value field. Show the position count instead
  // as a proxy until the backend adds total_aum to the response.
  const total = positions.reduce((s, p) => s + p.pct_of_portfolio, 0);
  return `${Math.round(total)}% allocated`;
}

/** Find the cash sleeve percentage. */
function cashSleeve(positions: HouseholdPosition[]): string {
  const cash = positions
    .filter((p) => p.asset_class.toLowerCase() === 'cash')
    .reduce((s, p) => s + p.pct_of_portfolio, 0);
  return cash > 0 ? `${Math.round(cash * 10) / 10}%` : '0%';
}

/* ── Client 360 panel ───────────────────────────────────────────────── */

interface ClientContextPanelProps {
  selectedItem: QueueItemSummary | null;
  household: HouseholdSummary | null;
  fetchStatus: Client360FetchStatus;
  fetchError: string | null;
}

function ClientContextPanel({ selectedItem, household, fetchStatus, fetchError }: ClientContextPanelProps) {
  const allocation = useMemo(
    () => (household ? buildAllocation(household.positions) : []),
    [household],
  );

  return (
    <aside className="slds-card" aria-label="Client 360">
      <div className="slds-card__header">
        <span>Client 360{selectedItem ? ` · ${selectedItem.title.slice(0, 30)}` : ''}</span>
        <span style={{ fontSize: 10, color: fetchStatus === 'error' ? 'var(--v6-error, #dc2626)' : 'var(--v6-success)', textTransform: 'none', letterSpacing: 0 }}>
          {fetchStatus === 'loading' ? '◌ loading…' : fetchStatus === 'error' ? '● error' : '● synced'}
        </span>
      </div>
      <div className="slds-card__body">
        {!selectedItem ? (
          <div className="slds-card__empty">
            Select an item in the Actions queue to see client context. Holdings, IPS allocation,
            and concentration signals render here.
          </div>
        ) : (
          <>
            <div className="v6-client360__head">
              <div className="v6-client360__avatar">
                {(household?.household_name ?? selectedItem.title)
                  .split(/[\s·]+/)
                  .slice(0, 2)
                  .map((w) => w[0])
                  .filter(Boolean)
                  .join('')
                  .slice(0, 2)
                  .toUpperCase() || 'CL'}
              </div>
              <div>
                <div className="v6-client360__name">{household?.household_name ?? selectedItem.title}</div>
                <div className="v6-client360__sub">{selectedItem.subtitle ?? 'Client · Wealth'}</div>
              </div>
            </div>
            <div className="v6-client360__section">
              <div className="v6-client360__section-title">Holdings overview</div>
              <div className="v6-client360__row">
                <span className="v6-client360__row-label">Total AUM</span>
                <span className="v6-client360__row-value">
                  {household ? formatAum(household.positions) : '—'}
                </span>
              </div>
              <div className="v6-client360__row">
                <span className="v6-client360__row-label">Cash sleeve</span>
                <span className="v6-client360__row-value">
                  {household ? cashSleeve(household.positions) : '—'}
                </span>
              </div>
              {fetchStatus === 'loading' && (
                <div className="slds-card__empty" style={{ paddingTop: 8 }}>
                  Fetching household data from CRM…
                </div>
              )}
              {fetchStatus === 'error' && (
                <div className="slds-card__empty" style={{ paddingTop: 8, color: 'var(--v6-error, #dc2626)' }}>
                  {fetchError ?? 'Failed to load household data.'}
                </div>
              )}
              {fetchStatus === 'idle' && !household && (
                <div className="slds-card__empty" style={{ paddingTop: 8 }}>
                  Holdings populate when the CRM MCP call for this household returns.
                </div>
              )}
            </div>
            <div className="v6-client360__section">
              <div className="v6-client360__section-title">Allocation vs. IPS</div>
              {allocation.length > 0 ? (
                <>
                  <div className="v6-alloc-bar">
                    {allocation.map((b) => (
                      <div
                        key={b.label}
                        className="v6-alloc-bar__seg"
                        style={{ width: `${b.pct}%`, background: b.color }}
                      />
                    ))}
                  </div>
                  <div className="v6-alloc-key">
                    {allocation.map((b) => (
                      <div key={b.label} className="v6-alloc-key__item">
                        <span className="v6-alloc-key__dot" style={{ background: b.color }} />
                        {b.label} {b.pct}%
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <div className="v6-alloc-bar">
                    <div className="v6-alloc-bar__seg" style={{ width: '62%', background: 'var(--v6-brand)' }} />
                    <div className="v6-alloc-bar__seg" style={{ width: '22%', background: 'var(--v6-success)' }} />
                    <div className="v6-alloc-bar__seg" style={{ width: '9%', background: '#8b5cf6' }} />
                    <div className="v6-alloc-bar__seg" style={{ width: '4%', background: 'var(--v6-warning)' }} />
                    <div className="v6-alloc-bar__seg" style={{ width: '3%', background: 'var(--v6-text-secondary)' }} />
                  </div>
                  <div className="v6-alloc-key">
                    <div className="v6-alloc-key__item">
                      <span className="v6-alloc-key__dot" style={{ background: 'var(--v6-brand)' }} />
                      Equity 62%
                    </div>
                    <div className="v6-alloc-key__item">
                      <span className="v6-alloc-key__dot" style={{ background: 'var(--v6-success)' }} />
                      Fixed 22%
                    </div>
                    <div className="v6-alloc-key__item">
                      <span className="v6-alloc-key__dot" style={{ background: '#8b5cf6' }} />
                      Alts 9%
                    </div>
                    <div className="v6-alloc-key__item">
                      <span className="v6-alloc-key__dot" style={{ background: 'var(--v6-warning)' }} />
                      RE 4%
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="v6-client360__section">
              <div className="v6-client360__section-title">Recent signals</div>
              {household?.recent_changes_pct && household.recent_changes_pct.length > 0 ? (
                <div style={{ fontSize: 12 }}>
                  {household.recent_changes_pct.map((c) => (
                    <div key={c.ticker} className="v6-client360__row">
                      <span className="v6-client360__row-label">{c.ticker} 30d</span>
                      <span
                        className="v6-client360__row-value"
                        style={{ color: c.change_pct_30d < 0 ? 'var(--v6-error, #dc2626)' : 'var(--v6-success)' }}
                      >
                        {c.change_pct_30d > 0 ? '+' : ''}{c.change_pct_30d}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="slds-card__empty">
                  {household
                    ? 'No recent signals for this household.'
                    : 'Signals populate from CRM + compliance_sweep skill when the household id is resolved.'}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

/* ── Main component ─────────────────────────────────────────────────── */

export interface AdvisorWorkbenchV6Props {
  onAuthExpired?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function AdvisorWorkbenchV6({ onAuthExpired, theme, onToggleTheme }: AdvisorWorkbenchV6Props) {
  const [pendingPlan, setPendingPlan] = useState<ActionPlan | null>(null);
  const [query, setQuery] = useState('');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [spineOpen, setSpineOpen] = useState(true);
  const [household, setHousehold] = useState<HouseholdSummary | null>(null);
  const [householdStatus, setHouseholdStatus] = useState<Client360FetchStatus>('idle');
  const [householdError, setHouseholdError] = useState<string | null>(null);
  const principalId = useSessionStore((s) => s.principalId) ?? 'anonymous';
  const sessionToken = useSessionStore((s) => s.sessionToken);
  const gateTracker = useGateTracker();
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;
  const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;

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
    onQueueUpdate: (ev) => {
      const queues = useQueuesStore.getState();
      if (ev.op === 'remove') {
        queues.removeItem(ev.queue, ev.item_id);
        return;
      }
      if (ev.item) {
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

  /* ── Fetch household data when selectedItem changes ─────────────── */

  const fetchHousehold = useCallback(
    async (item: QueueItemSummary, signal: AbortSignal) => {
      // Use client_contact_id when available; fall back to the queue item id.
      const householdId = item.client_contact_id ?? item.id;
      if (!apiUrl || !sessionToken) return;

      setHouseholdStatus('loading');
      setHouseholdError(null);
      setHousehold(null);

      try {
        const res = await fetch(`${apiUrl}/mcp/salesforce-crm/tools/call`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify({
            name: 'read_household_summary',
            arguments: { household_id: householdId },
          }),
          signal,
        });

        if (!res.ok) {
          throw new Error(`CRM MCP returned ${res.status}`);
        }

        const data = (await res.json()) as HouseholdSummary;
        if (!signal.aborted) {
          setHousehold(data);
          setHouseholdStatus('loaded');
        }
      } catch (err: unknown) {
        if (signal.aborted) return;
        const message = err instanceof Error ? err.message : 'Unknown error';
        setHouseholdError(message);
        setHouseholdStatus('error');
      }
    },
    [apiUrl, sessionToken],
  );

  useEffect(() => {
    if (!selectedItem) {
      setHousehold(null);
      setHouseholdStatus('idle');
      setHouseholdError(null);
      return;
    }
    const controller = new AbortController();
    void fetchHousehold(selectedItem, controller.signal);
    return () => controller.abort();
  }, [selectedItem, fetchHousehold]);

  return (
    <ErrorBoundary>
      <div className="v6-advisor" data-testid="v6-advisor">
        <PersonaHeaderV6 persona="fsi_advisor" theme={theme} onToggleTheme={onToggleTheme} />

        {planInFlight && (
          <div className="v4-root" style={{ padding: '0 0.75rem' }}>
            <GatesTrackerV4 gates={gateTracker.gates} />
          </div>
        )}

        <div className="v6-advisor__body">
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
          <ClientContextPanel
            selectedItem={selectedItem}
            household={household}
            fetchStatus={householdStatus}
            fetchError={householdError}
          />
        </div>

        <SampleQueries
          categories={ADVISOR_QUERIES}
          onSelect={(text) => {
            setQuery(text);
            queueMicrotask(() => {
              reset();
              send({ type: 'turn', turn_id: crypto.randomUUID(), text });
            });
          }}
        />

        <div className="v6-trust-spine">
          <details
            open={spineOpen || undefined}
            onToggle={(e) => setSpineOpen((e.target as HTMLDetailsElement).open)}
            data-testid="v6-trust-spine"
          >
            <summary>
              <span>
                <strong>Trust spine</strong> · same orchestrator graph as Sarah's research, now lit
                through advisor_orch
              </span>
              <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                {pendingPlan ? `plan ${pendingPlan.plan_id.slice(0, 8)} · gate ④ HITL` : ''}
              </span>
            </summary>
            <div className="v6-trust-spine__content v4-root">
              <TraversalMapV4 persona="fsi_advisor" langfuseBaseUrl={langfuseBaseUrl} />
              <TimelineV4 persona="fsi_advisor" gates={gateTracker.gates} langfuseBaseUrl={langfuseBaseUrl} />
            </div>
          </details>
        </div>

        <div className="v6-audit-wrap v4-root">
          <AuditStripV4 />
        </div>
      </div>
    </ErrorBoundary>
  );
}

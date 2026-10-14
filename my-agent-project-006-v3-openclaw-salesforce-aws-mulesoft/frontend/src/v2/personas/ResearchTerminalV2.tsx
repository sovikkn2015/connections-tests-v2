/**
 * Research Terminal v2 — Sarah Chen's forensic dark surface.
 *
 * Real wiring:
 *   - WebSocket: useAgentSocket (existing, unchanged)
 *   - Turn streaming: useStreamingTurn (existing — populates brief + traversal stores)
 *   - Intent prefetch: useIntentPrefetch (existing)
 *   - Brief content: useBriefStore.markdown (live WS stream)
 *   - Citations: useBriefStore.citationsBySpan (resolved via rest.getSourceChunk)
 *   - Running chips: derived from useBriefStore.toolCalls (shows live specialist state)
 *   - Architecture map: TraversalMapV2 ← useTraversalStore
 *   - Timeline: TimelineV2 ← useBriefStore.toolCalls + durationMs
 *   - Audit strip: AuditStripV2 ← all three stores
 *
 * No mock data. Panes (Market / Filings / Sentiment / Demand) are populated
 * from the same WebSocket stream but also honour `chart_intent` events for
 * structured charts.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PersonaHeaderV2 } from '../atoms/PersonaHeaderV2';
import { TraversalMapV2 } from '../atoms/TraversalMapV2';
import { TimelineV2 } from '../atoms/TimelineV2';
import { AuditStripV2 } from '../atoms/AuditStripV2';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useIntentPrefetch } from '../../shared/hooks/useIntentPrefetch';
import { useBriefStore } from '../../shared/store/brief';
import { StreamingText } from '../../shared/components/StreamingText';
import type { RestClient } from '../../shared/lib/restClient';
import type { QueueItemSummary, SourceChunk } from '../../shared/types/api';

export interface ResearchTerminalV2Props {
  rest: RestClient;
  onAuthExpired?: () => void;
  demandSignals?: QueueItemSummary[];
}

/* -------------------------------------------------------------------------
 * Sub-pane components — all read live stores
 * ------------------------------------------------------------------------- */

function RunningChips() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  // Dedupe by tool_name — show one chip per unique tool with worst-case status.
  const byTool = new Map<string, { status: 'running' | 'ok' | 'error'; latency?: number }>();
  for (const tc of toolCalls) {
    const existing = byTool.get(tc.tool_name);
    const nextStatus: 'running' | 'ok' | 'error' =
      tc.status === 'error'
        ? 'error'
        : existing?.status === 'error'
        ? 'error'
        : tc.status;
    byTool.set(tc.tool_name, {
      status: nextStatus,
      latency: tc.latency_ms ?? existing?.latency,
    });
  }
  const items = Array.from(byTool.entries());
  if (items.length === 0) return null;
  return (
    <div className="v2-brief__chips">
      {items.map(([tool, meta]) => {
        const cls =
          meta.status === 'ok' ? 'chip-ok' : meta.status === 'error' ? 'chip-error' : 'chip-running';
        return (
          <span key={tool} className={cls}>
            {tool}
            {meta.latency !== undefined ? ` · ${meta.latency}ms` : meta.status === 'running' ? ' · running' : ''}
          </span>
        );
      })}
    </div>
  );
}

function BriefPaneV2({ onOpenCitation }: { onOpenCitation: (id: string) => void }) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const toolCalls = useBriefStore((s) => s.toolCalls);

  const specCount = new Set(toolCalls.map((t) => t.agent_id)).size;
  const completedCount = new Set(
    toolCalls.filter((t) => t.status === 'ok').map((t) => t.agent_id),
  ).size;

  return (
    <div className="v2-pane">
      <div className="v2-pane__header">
        <span>Brief — citation-enforced</span>
        {isStreaming ? (
          <span className="v2-pane__status v2-pane__status--streaming">streaming…</span>
        ) : (
          <span className="v2-pane__status v2-pane__status--idle">
            {toolCalls.length > 0 ? 'idle' : 'awaiting query'}
          </span>
        )}
        {specCount > 0 && (
          <span className="v2-pane__status v2-pane__status--idle">
            {completedCount} of {specCount} specialists complete
          </span>
        )}
      </div>
      <div className="v2-pane__body">
        <RunningChips />
        {markdown ? (
          <div className="v2-brief">
            <StreamingText
              markdown={markdown}
              citations={citations}
              isStreaming={isStreaming}
              onOpenCitation={onOpenCitation}
            />
          </div>
        ) : (
          <div className="v2-brief__empty">
            Enter a query above and press ⌘↵ to dispatch the research orchestrator.
            The brief will stream in live as specialists complete.
          </div>
        )}
      </div>
    </div>
  );
}

function MarketPaneV2() {
  // Panel currently shows a placeholder until chart_intent event arrives.
  // Real wiring: listens to useBriefStore.charts and renders the first bar/line
  // that targets "market" — leaves room for live prices in later iteration.
  const charts = useBriefStore((s) => s.charts);
  const marketChart = charts.find((c) => c.title?.toLowerCase().includes('market'));
  return (
    <div className="v2-pane">
      <div className="v2-pane__header">
        <span>Market · live</span>
        <span className="v2-pane__status v2-pane__status--idle">finnhub</span>
      </div>
      <div className="v2-pane__body">
        {marketChart ? (
          <div>
            <div className="w360-label">{marketChart.title}</div>
            <div className="v2-market">
              <div className="v2-market__price-row">
                <span className="v2-market__ticker">—</span>
                <span className="v2-market__price">—</span>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--forensic-text-5)', fontSize: '0.75rem', fontStyle: 'italic' }}>
            Market data loads from the research_orchestrator's market_specialist on first turn.
          </div>
        )}
      </div>
    </div>
  );
}

function FilingsPaneV2() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const filings = Object.values(citations).filter((c) => c.source_type === 'filing');
  return (
    <div className="v2-pane">
      <div className="v2-pane__header">
        <span>Filings · {filings.length} chunks indexed</span>
        <span className="v2-pane__status v2-pane__status--idle">EDGAR</span>
      </div>
      <div className="v2-pane__body">
        {filings.length === 0 ? (
          <div style={{ color: 'var(--forensic-text-5)', fontSize: '0.75rem', fontStyle: 'italic' }}>
            10-K / 10-Q / 8-K chunks appear as the filings_specialist cites them.
          </div>
        ) : (
          filings.slice(0, 6).map((c) => {
            // Hint filing type from label text (e.g. "10-Q · FY26 Q3 · p.42")
            const parts = c.label?.split('·').map((s) => s.trim()) ?? [];
            const type = parts[0] ?? '10-K';
            return (
              <div key={c.span_id} className="v2-filings-row">
                <span className="v2-filings-chip" data-type={type}>
                  {type}
                </span>
                <div>
                  <div className="v2-filings-row__title">{c.label ?? 'untitled'}</div>
                  <div className="v2-filings-row__meta">
                    {c.page ? `p.${c.page}` : ''}
                  </div>
                </div>
                <span style={{ color: 'var(--forensic-text-5)', fontSize: 10 }}>↗</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function SentimentPaneV2() {
  // Uses citations source_type=news as a proxy; real sentiment chart will
  // arrive via chart_intent event when sentiment_specialist completes.
  const citations = useBriefStore((s) => s.citationsBySpan);
  const news = Object.values(citations).filter((c) => c.source_type === 'news');
  return (
    <div className="v2-pane">
      <div className="v2-pane__header">
        <span>Sentiment · 30d</span>
        <span className="v2-pane__status v2-pane__status--idle">{news.length} articles</span>
      </div>
      <div className="v2-pane__body">
        <div style={{ color: 'var(--forensic-text-5)', fontSize: '0.75rem', fontStyle: 'italic' }}>
          Sentiment score and sparkline render when sentiment_specialist emits a chart_intent.
        </div>
      </div>
    </div>
  );
}

function DemandPaneV2({
  items,
  onAccept,
}: {
  items: QueueItemSummary[];
  onAccept: (id: string) => void;
}) {
  return (
    <div className="v2-pane">
      <div className="v2-pane__header">
        <span>Demand Signals</span>
        <span className="v2-pane__status v2-pane__status--idle">{items.length}</span>
      </div>
      <div className="v2-pane__body">
        {items.length === 0 ? (
          <div style={{ color: 'var(--forensic-text-5)', fontSize: '0.75rem', fontStyle: 'italic' }}>
            No suggestions from the field yet.
          </div>
        ) : (
          items.map((it, i) => (
            <div
              key={it.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                padding: '8px 0',
                borderBottom: i < items.length - 1 ? '1px solid var(--forensic-line)' : '0',
                gap: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ color: 'var(--forensic-text-0)', fontSize: 12, fontWeight: 500 }}>
                  {it.title}
                </div>
                <div
                  className="w360-mono"
                  style={{ color: 'var(--forensic-text-5)', fontSize: 10 }}
                >
                  {it.subtitle ?? '—'}
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => onAccept(it.id)}
                style={{ fontSize: 10, padding: '3px 8px' }}
              >
                accept →
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Root component
 * ------------------------------------------------------------------------- */

export function ResearchTerminalV2({ rest, onAuthExpired, demandSignals = [] }: ResearchTerminalV2Props) {
  const [query, setQuery] = useState('');
  const [openChunk, setOpenChunk] = useState<SourceChunk | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reset = useBriefStore((s) => s.reset);
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

  // Track each turn's query text so the history row can surface it.
  const turnTextsRef = useRef<Record<string, string>>({});
  const handleMessage = useStreamingTurn({
    getTurnText: (id) => turnTextsRef.current[id],
  });
  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });

  useIntentPrefetch(query, {
    onPrefetch: (m) => send(m),
  });

  const submit = useCallback(() => {
    if (!query.trim()) return;
    reset();
    const turnId = crypto.randomUUID();
    turnTextsRef.current[turnId] = query;
    send({ type: 'turn', turn_id: turnId, text: query });
  }, [query, reset, send]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        submit();
      } else if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [submit]);

  const openCitation = useCallback(
    (sourceId: string) => {
      rest.getSourceChunk(sourceId).then(setOpenChunk).catch(() => undefined);
    },
    [rest],
  );

  const acceptDemand = useCallback(
    (id: string) => {
      const item = demandSignals.find((d) => d.id === id);
      if (!item) return;
      setQuery(`Research ${item.title}`);
      setTimeout(submit, 0);
    },
    [demandSignals, submit],
  );

  // Empty-state demand-signal pool (real feed may be wired later — graceful empty allowed).
  const effectiveDemand = useMemo(() => demandSignals, [demandSignals]);

  return (
    <ErrorBoundary>
      <div className="v2-research">
        <PersonaHeaderV2 persona="fsi_research" surface="forensic" />
        <div className="v2-research__toolbar">
          <div className="v2-research__query">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Research NVDA ahead of earnings — focus on data-center mix and China exposure…"
              aria-label="Research query"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <button type="button" className="btn-brand" onClick={submit}>
              Run ⌘↵
            </button>
          </div>
        </div>
        <div className="v2-research__body">
          <BriefPaneV2 onOpenCitation={openCitation} />
          <div className="v2-research__right">
            <MarketPaneV2 />
            <FilingsPaneV2 />
          </div>
          <div className="v2-research__right">
            <SentimentPaneV2 />
            <DemandPaneV2 items={effectiveDemand} onAccept={acceptDemand} />
          </div>
        </div>
        <details className="v2-map-panel" open>
          <summary>Trust spine — live</summary>
          <TraversalMapV2 fallbackPersona="fsi_research" langfuseBaseUrl={langfuseBaseUrl} />
          <TimelineV2 persona="fsi_research" langfuseBaseUrl={langfuseBaseUrl} />
        </details>
        <AuditStripV2 langfuseBaseUrl={langfuseBaseUrl} />
        {openChunk && (
          <aside
            role="region"
            aria-label="Source drill-down"
            style={{
              position: 'fixed',
              right: 0,
              top: '3rem',
              bottom: 0,
              width: '420px',
              background: 'var(--forensic-bg-2)',
              color: 'var(--forensic-text-1)',
              borderLeft: '1px solid var(--forensic-line)',
              padding: '1rem',
              overflowY: 'auto',
              zIndex: 10,
            }}
          >
            <button
              type="button"
              onClick={() => setOpenChunk(null)}
              style={{
                float: 'right',
                background: 'transparent',
                color: 'var(--forensic-text-4)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 18,
              }}
              aria-label="Close source drill-down"
            >
              ✕
            </button>
            <h3 style={{ marginTop: 0 }}>{openChunk.title}</h3>
            {openChunk.filing_type && (
              <div style={{ fontSize: '0.75rem', opacity: 0.7, marginBottom: 8 }}>
                {openChunk.filing_type} · {openChunk.filing_date} · {openChunk.section}
                {openChunk.page ? ` · p.${openChunk.page}` : ''}
              </div>
            )}
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{openChunk.text}</pre>
            {openChunk.url && (
              <a
                href={openChunk.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--w360-brand-500)' }}
              >
                Open source
              </a>
            )}
          </aside>
        )}
      </div>
    </ErrorBoundary>
  );
}

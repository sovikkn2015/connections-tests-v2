/**
 * Research Terminal V4 — Sarah Chen's forensic dark terminal.
 *
 * Layout follows V2's organisation (the one that reads cleanly in the
 * live screenshots): brief wide-left + two 320px right rails each
 * stacking two panes. Trust spine sits BELOW the body in one collapsible
 * panel that holds the Architecture Map stacked over the End-to-End
 * Timeline — not side-by-side, which cramped both at real viewport
 * widths.
 *
 * Typography and chrome stay V4 (44/44/28 bars, 11/12/13 type ramp,
 * JetBrains Mono + tabular-nums, uppercase labels with 0.06em tracking,
 * flat 1px borders) — what was right in V4 stays; what was wrong in
 * V4 (side-by-side trace, 3-pane right rail, extra Specialists card)
 * is gone.
 *
 * Wired for production:
 *  - Query submit triggers `useAgentSocket.send({ type: 'turn' })`
 *  - Brief text streams from `useBriefStore.markdown`
 *  - Running chips track real tool_call spans (status + latency)
 *  - Market pane pulls last market-data tool span
 *  - Filings pane reads citation store filtered on source_type='filing'
 *  - Sentiment pane reads citation store filtered on source_type='news'
 *  - Demand pane reads `useQueuesStore.itemsByQueue.briefs`
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { PersonaHeaderV4 } from '../atoms/PersonaHeaderV4';
import { TrustSpineV4 } from '../atoms/TrustSpineV4';
import { AuditStripV4 } from '../atoms/AuditStripV4';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';
import { useQueuesStore } from '../../shared/store/queues';
import { StreamingText } from '../../shared/components/StreamingText';
import type { ToolCall, SourceChunk } from '../../shared/types/api';

function RunningChips() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const byTool = new Map<string, { status: ToolCall['status']; latency?: number }>();
  for (const tc of toolCalls) {
    const existing = byTool.get(tc.tool_name);
    const nextStatus: ToolCall['status'] =
      tc.status === 'error' ? 'error' : existing?.status === 'error' ? 'error' : tc.status;
    byTool.set(tc.tool_name, {
      status: nextStatus,
      latency: tc.latency_ms ?? existing?.latency,
    });
  }
  const items = Array.from(byTool.entries());
  if (items.length === 0) return null;
  return (
    <div className="brief-chips-row">
      {items.map(([tool, meta]) => (
        <span key={tool} className="chip-running" data-status={meta.status}>
          {tool}
          {meta.latency !== undefined
            ? ` · ${meta.latency}ms`
            : meta.status === 'running'
              ? ' · running'
              : ''}
        </span>
      ))}
    </div>
  );
}

function BriefPane({ onOpenCitation }: { onOpenCitation: (id: string) => void }) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const toolCalls = useBriefStore((s) => s.toolCalls);

  const specCount = new Set(toolCalls.map((t) => t.agent_id)).size;
  const completedCount = new Set(toolCalls.filter((t) => t.status === 'ok').map((t) => t.agent_id))
    .size;

  const statusKind: 'streaming' | 'idle' = isStreaming ? 'streaming' : 'idle';
  const statusText = isStreaming ? 'streaming…' : toolCalls.length > 0 ? 'idle' : 'awaiting query';

  return (
    <div className="pane">
      <div className="pane__header">
        <span>Brief — citation-enforced</span>
        <span className={`pane__status pane__status--${statusKind}`}>● {statusText}</span>
        {specCount > 0 && (
          <span className="pane__status pane__status--idle" style={{ marginLeft: 'auto' }}>
            {completedCount} of {specCount} specialists complete
          </span>
        )}
      </div>
      <div className="pane__body">
        <RunningChips />
        {markdown ? (
          <div className="research-brief">
            <StreamingText
              markdown={markdown}
              citations={citations}
              isStreaming={isStreaming}
              onOpenCitation={onOpenCitation}
            />
          </div>
        ) : (
          <div className="brief-empty">
            Type a query above and press ⌘↵. Research orchestrator will dispatch market_specialist,
            filings_specialist, sentiment_specialist, statement_specialist, and compliance_specialist
            in parallel — brief streams in as each returns.
          </div>
        )}
      </div>
    </div>
  );
}

function MarketPane() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const lastMarket = toolCalls.filter((tc) => tc.tool_name.includes('quote') || tc.tool_name.includes('market')).slice(-1)[0];
  const statusKind = !lastMarket ? 'idle' : lastMarket.status === 'running' ? 'streaming' : 'idle';
  const statusLabel = !lastMarket
    ? 'awaiting turn'
    : lastMarket.status === 'running'
      ? 'live'
      : lastMarket.status === 'ok'
        ? 'cached'
        : 'error';

  return (
    <div className="pane" style={{ flex: 1 }}>
      <div className="pane__header">
        <span>Market · live</span>
        <span className={`pane__status pane__status--${statusKind}`}>● {statusLabel}</span>
      </div>
      <div className="pane__body" style={{ padding: '12px 14px' }}>
        {!lastMarket ? (
          <div style={{ color: 'var(--v4-forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
            Market data loads once the market_specialist fires on the next turn.
          </div>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 4,
              }}
            >
              <span style={{ fontSize: 22, fontWeight: 700, color: '#fff' }}>
                {lastMarket.tool_name.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 4) || 'TICKER'}
              </span>
              <span
                className="w360-mono"
                style={{ fontSize: 14, color: 'var(--v4-forensic-text-3)' }}
              >
                finnhub · {lastMarket.latency_ms ?? '…'}ms
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--v4-forensic-text-4)' }}>
              Quote payload recorded in Langfuse trace — click the corresponding node on the map
              to inspect.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function FilingsPane() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const filings = Object.values(citations).filter((c) => c.source_type === 'filing');
  return (
    <div className="pane" style={{ flex: 1 }}>
      <div className="pane__header">
        <span>Filings · {filings.length} chunks indexed</span>
        <span className="pane__status pane__status--idle">EDGAR</span>
      </div>
      <div className="pane__body" style={{ padding: '10px 14px' }}>
        {filings.length === 0 ? (
          <div style={{ color: 'var(--v4-forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
            10-K / 10-Q / 8-K chunks appear as the filings_specialist cites them.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: '4px 10px', fontSize: 12 }}>
            {filings.slice(0, 6).map((c) => {
              const parts = c.label?.split('·').map((s) => s.trim()) ?? [];
              const type = parts[0] ?? '10-K';
              return (
                <div key={c.span_id} style={{ display: 'contents' }}>
                  <span
                    className="w360-mono"
                    style={{
                      color: 'var(--v4-brand-500)',
                      fontSize: 10,
                      padding: '2px 6px',
                      borderRadius: 2,
                      background: 'rgba(27,150,255,0.08)',
                      border: '1px solid rgba(27,150,255,0.2)',
                      textAlign: 'center',
                    }}
                  >
                    {type}
                  </span>
                  <div style={{ color: '#fff', fontSize: 12 }}>{c.label ?? 'untitled'}</div>
                  <span style={{ color: 'var(--v4-forensic-text-5)', fontSize: 10 }}>↗</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function SentimentPane() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const news = Object.values(citations).filter((c) => c.source_type === 'news');
  return (
    <div className="pane" style={{ flex: 1 }}>
      <div className="pane__header">
        <span>Sentiment · 30d</span>
        <span className="pane__status pane__status--idle">{news.length} articles</span>
      </div>
      <div className="pane__body" style={{ padding: '10px 14px' }}>
        <div style={{ color: 'var(--v4-forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
          Sentiment score and sparkline render when sentiment_specialist emits a chart_intent.
        </div>
      </div>
    </div>
  );
}

function DemandPane() {
  const queueItems = useQueuesStore((s) => s.itemsByQueue);
  // Demand signals come from both the 'briefs' queue (research suggestions)
  // and the 'alerts' queue (client inquiries routed to research via rm_handoff).
  // Act 3 of the demo script requires Client_Inquiry__c items to appear here.
  const briefItems = queueItems.briefs ?? [];
  const alertItems = (queueItems.alerts ?? []).filter(
    (it) => it.subtitle?.toLowerCase().includes('inquiry') || it.subtitle?.toLowerCase().includes('research'),
  );
  const items = [...alertItems, ...briefItems];
  return (
    <div className="pane" style={{ flex: 1 }}>
      <div className="pane__header">
        <span>Demand Signals</span>
        <span className="pane__status pane__status--idle">{items.length}</span>
      </div>
      <div className="pane__body" style={{ padding: '6px 14px' }}>
        {items.length === 0 ? (
          <div style={{ color: 'var(--v4-forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
            No suggestions from the field yet. Demand signals are rolled up from client inquiries by
            ticker.
          </div>
        ) : (
          items.map((it) => (
            <div
              key={it.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                padding: '8px 0',
                borderBottom: '1px solid var(--v4-forensic-line)',
                gap: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ color: '#fff', fontSize: 12, fontWeight: 500 }}>{it.title}</div>
                {it.subtitle && (
                  <div
                    className="w360-mono"
                    style={{ color: 'var(--v4-forensic-text-4)', fontSize: 10 }}
                  >
                    {it.subtitle}
                  </div>
                )}
              </div>
              {it.badge && (
                <span
                  className="w360-mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--v4-brand-500)',
                    border: '1px solid var(--v4-brand-500)',
                    padding: '1px 6px',
                    borderRadius: 3,
                  }}
                >
                  {it.badge}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export interface ResearchTerminalV4Props {
  onAuthExpired?: () => void;
}

export function ResearchTerminalV4({ onAuthExpired }: ResearchTerminalV4Props) {
  const [query, setQuery] = useState('');
  const [openChunk, setOpenChunk] = useState<SourceChunk | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reset = useBriefStore((s) => s.reset);
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

  const turnTextsRef = useRef<Record<string, string>>({});
  const handleMessage = useStreamingTurn({
    getTurnText: (id) => turnTextsRef.current[id],
    // Demand Signals pane reads useQueuesStore.itemsByQueue.briefs — wire
    // backend queue_update events into the store so the field's research
    // suggestions populate live. Matches advisor-side wiring.
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

  const openCitation = useCallback((sourceId: string) => {
    // V4: open citation drill-down side panel. Fetches the real source
    // chunk from the sec-edgar MCP and renders it in a slide-over drawer.
    // For now, open in a simple alert-style overlay until the full drawer
    // component is ported from v2.
    const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
    const token = useSessionStore.getState().sessionToken ?? '';
    fetch(`${apiUrl}/api/source_chunk/${encodeURIComponent(sourceId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((chunk) => {
        setOpenChunk(chunk);
      })
      .catch(() => {
        /* silent — citation drill-down is best-effort */
      });
  }, []);

  const onInputKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  };

  const eyebrowRight = useMemo(
    () => 'conversation ↔ orchestrator graph',
    [],
  );

  return (
    <ErrorBoundary>
      <div className="research-root" data-testid="v4-research">
        <PersonaHeaderV4 persona="fsi_research" />
        <div className="research-toolbar">
          <div className="research-query">
            <input
              ref={inputRef}
              className="research-query__input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Research NVDA ahead of earnings — focus on data-center mix and China exposure…"
              aria-label="Research query"
              onKeyDown={onInputKey}
            />
            <button type="button" className="btn-brand" onClick={submit} disabled={!query.trim()}>
              Run ⌘↵
            </button>
          </div>
          <button type="button" className="btn-ghost" title="View raw envelope (v5)">
            {'{ }'} JSON
          </button>
        </div>
        <div className="research-body">
          <BriefPane onOpenCitation={openCitation} />
          <div className="research-body__rail">
            <MarketPane />
            <FilingsPane />
          </div>
          <div className="research-body__rail">
            <SentimentPane />
            <DemandPane />
          </div>
        </div>
        <TrustSpineV4
          persona="fsi_research"
          eyebrowRight={eyebrowRight}
          langfuseBaseUrl={langfuseBaseUrl}
        />
        <AuditStripV4 />
        {openChunk && (
          <aside
            role="region"
            aria-label="Source drill-down"
            style={{
              position: 'fixed',
              right: 0,
              top: '3rem',
              bottom: 0,
              width: 420,
              background: 'var(--v4-forensic-bg-2, #1a1a2e)',
              color: 'var(--v4-forensic-text-1, #e0e0e0)',
              borderLeft: '1px solid var(--v4-forensic-line, #333)',
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
                color: 'var(--v4-forensic-text-4, #888)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 18,
              }}
              aria-label="Close source drill-down"
            >
              ✕
            </button>
            <h3 style={{ marginTop: 0 }}>{openChunk.title || openChunk.source_id}</h3>
            {openChunk.filing_type && (
              <div style={{ fontSize: '0.75rem', opacity: 0.7, marginBottom: 8 }}>
                {openChunk.filing_type} · {openChunk.filing_date} · {openChunk.section}
                {openChunk.page ? ` · p.${openChunk.page}` : ''}
              </div>
            )}
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 12 }}>
              {openChunk.text || '(source not available)'}
            </pre>
          </aside>
        )}
      </div>
    </ErrorBoundary>
  );
}

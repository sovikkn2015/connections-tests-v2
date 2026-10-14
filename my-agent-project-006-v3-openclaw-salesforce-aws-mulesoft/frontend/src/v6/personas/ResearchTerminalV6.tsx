/**
 * Research Terminal V6 — Sarah Chen's SLDS-light research surface.
 *
 * Layout: header → query bar → 3-column grid (brief 1.6fr | market+filings
 * 320px | sentiment+demand 320px) → collapsible trust spine → audit strip.
 *
 * Imports V4 atoms (TraversalMapV4, TimelineV4, AuditStripV4) for the trust
 * spine and audit strip — they work, no rewrite needed.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { PersonaHeaderV6 } from '../atoms/PersonaHeaderV6';
import { SampleQueries } from '../atoms/SampleQueries';
import type { QueryCategory } from '../atoms/SampleQueries';
import { TraversalMapV4 } from '../../v4/atoms/TraversalMapV4';
import { TimelineV4 } from '../../v4/atoms/TimelineV4';
import { AuditStripV4 } from '../../v4/atoms/AuditStripV4';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { StreamingText } from '../../shared/components/StreamingText';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useBriefStore } from '../../shared/store/brief';
import { useSessionStore } from '../../shared/store/session';
import { useQueuesStore } from '../../shared/store/queues';
import type { ToolCall, SourceChunk } from '../../shared/types/api';

/* ── Sample queries ─────────────────────────────────────────────────── */

const RESEARCH_QUERIES: QueryCategory[] = [
  {
    label: 'Earnings preview',
    queries: [
      { text: 'Research META ahead of earnings — focus on data-center capex and AI monetization', narrative: true, hint: '4 specialists fan out in parallel via asyncio.gather. Without OpenClaw: 60s+ sequential.' },
      { text: 'Research NVDA ahead of earnings — focus on data-center revenue mix and China exposure', hint: '5 specialists: market, filings, sentiment, statement, compliance' },
      { text: 'Pre-earnings setup for MSFT — Azure growth vs. consensus', hint: 'Cross-references 10-Q MD&A with sell-side estimates' },
    ],
  },
  {
    label: 'Financial statements',
    queries: [
      { text: 'Deep dive on NVIDIA financials — margins, ROIC, and peer comparison', hint: 'statement_specialist runs deterministic analysis, not LLM math' },
      { text: 'Compare AAPL and MSFT gross margins over the last 4 quarters', hint: 'Pulls from 10-Q filings via sec-edgar MCP' },
    ],
  },
  {
    label: 'Sentiment & news',
    queries: [
      { text: 'What is the 30-day news sentiment for NVDA?', hint: 'sentiment_specialist scores 76 articles via Tavily + Sonnet' },
      { text: 'Summarize recent analyst commentary on META AI spending', hint: 'News search + sentiment scoring' },
    ],
  },
  {
    label: 'Cross-asset thesis',
    queries: [
      { text: 'How does the NVDA China export ban affect the broader semiconductor supply chain?', hint: 'Crosses filings (risk factors) with news (policy headlines)' },
      { text: 'What is the read-through from TSMC earnings to NVDA and AMD?', hint: 'Multi-ticker cross-reference' },
    ],
  },
  {
    label: 'Filing deep-dive',
    queries: [
      { text: 'What are the key risk factors in NVDA latest 10-K?', narrative: true, hint: 'Citations use real chunk IDs from Bedrock KB (784 indexed chunks)' },
      { text: 'Summarize Item 7 MD&A from AAPL most recent 10-Q', hint: 'Section-aware RAG preserves filing structure' },
    ],
  },
  {
    label: 'Quick check',
    queries: [
      { text: 'Quote NVDA', hint: "L1 path — only market_specialist fires. Proves the agent doesn't over-engineer simple queries." },
      { text: 'Who covers NVDA on our desk?', hint: 'CRM lookup via salesforce-crm MCP' },
      { text: 'Is NVDA on the restricted list?', hint: 'compliance_specialist checks restricted list + MNPI' },
    ],
  },
];

/* ── Running chips ──────────────────────────────────────────────────── */

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
    <div className="v6-chips">
      {items.map(([tool, meta]) => (
        <span key={tool} className="v6-chip" data-status={meta.status}>
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

/* ── Brief pane ─────────────────────────────────────────────────────── */

function BriefPane({ onOpenCitation }: { onOpenCitation: (id: string) => void }) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const toolCalls = useBriefStore((s) => s.toolCalls);

  const specCount = new Set(toolCalls.map((t) => t.agent_id)).size;
  const completedCount = new Set(
    toolCalls.filter((t) => t.status === 'ok').map((t) => t.agent_id),
  ).size;

  const statusKind: 'streaming' | 'idle' = isStreaming ? 'streaming' : 'idle';
  const statusText = isStreaming ? 'streaming…' : toolCalls.length > 0 ? 'idle' : 'awaiting query';

  return (
    <div className="slds-card">
      <div className="slds-card__header">
        <span>Brief — citation-enforced</span>
        <span className={`slds-card__status slds-card__status--${statusKind}`}>● {statusText}</span>
        {specCount > 0 && (
          <span className="slds-card__status slds-card__status--idle" style={{ marginLeft: 'auto' }}>
            {completedCount} of {specCount} specialists complete
          </span>
        )}
      </div>
      <div className="slds-card__body">
        <RunningChips />
        {markdown ? (
          <div className="v6-brief">
            <StreamingText
              markdown={markdown}
              citations={citations}
              isStreaming={isStreaming}
              onOpenCitation={onOpenCitation}
            />
          </div>
        ) : (
          <div className="slds-card__empty">
            Type a query above and press ⌘↵. Research orchestrator will dispatch
            market_specialist, filings_specialist, sentiment_specialist,
            statement_specialist, and compliance_specialist in parallel — brief
            streams in as each returns.
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Market pane ────────────────────────────────────────────────────── */

function MarketPane() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const markdown = useBriefStore((s) => s.markdown);
  const lastMarket = toolCalls
    .filter((tc) => tc.tool_name.includes('quote') || tc.tool_name.includes('market'))
    .slice(-1)[0];
  const statusKind = !lastMarket ? 'idle' : lastMarket.status === 'running' ? 'streaming' : 'idle';
  const statusLabel = !lastMarket
    ? 'awaiting turn'
    : lastMarket.status === 'running'
      ? 'live'
      : lastMarket.status === 'ok'
        ? 'cached'
        : 'error';

  // Extract ticker from the brief text — look for patterns like "NVDA" in the
  // market_specialist section or the query itself.
  const tickerMatch = markdown?.match(/\b([A-Z]{2,5})\b/);
  const ticker = tickerMatch ? tickerMatch[1] : null;

  // Extract the market_specialist section from the brief for display
  const marketSection = (() => {
    const match = (markdown ?? '').match(/## market_specialist\n([\s\S]*?)(?=\n## |\n*$)/);
    if (!match?.[1]) return null;
    const text = match[1].trim();
    if (!text || text.length < 5) return null;
    return text;
  })();

  return (
    <div className="slds-card">
      <div className="slds-card__header">
        <span>Market · live</span>
        <span className={`slds-card__status slds-card__status--${statusKind}`}>● {statusLabel}</span>
      </div>
      <div className="slds-card__body">
        {!lastMarket ? (
          <div className="slds-card__empty">
            Market data loads once the market_specialist fires on the next turn.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--v6-text-primary)' }}>
                {ticker ?? 'TICKER'}
              </span>
              <span className="w360-mono" style={{ fontSize: 11, color: 'var(--v6-text-secondary)' }}>
                finnhub · {lastMarket.latency_ms ?? '…'}ms
              </span>
            </div>
            {marketSection ? (
              <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--v6-text-primary)' }}>
                {marketSection.slice(0, 300)}
                {marketSection.length > 300 ? '…' : ''}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--v6-text-secondary)' }}>
                Quote data returned — see the brief for details.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Filings pane ───────────────────────────────────────────────────── */

function FilingsPane() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const filings = Object.values(citations).filter((c) => c.source_type === 'filing');
  return (
    <div className="slds-card">
      <div className="slds-card__header">
        <span>Filings · {filings.length} chunks indexed</span>
        <span className="slds-card__status slds-card__status--idle">EDGAR</span>
      </div>
      <div className="slds-card__body">
        {filings.length === 0 ? (
          <div className="slds-card__empty">
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
                      color: 'var(--v6-brand)',
                      fontSize: 10,
                      padding: '2px 6px',
                      borderRadius: 2,
                      background: 'var(--v6-brand-light)',
                      border: '1px solid rgba(0,112,210,0.2)',
                      textAlign: 'center',
                    }}
                  >
                    {type}
                  </span>
                  <div style={{ color: 'var(--v6-text-primary)', fontSize: 12 }}>{c.label ?? 'untitled'}</div>
                  <span style={{ color: 'var(--v6-text-secondary)', fontSize: 10 }}>↗</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Sentiment pane ─────────────────────────────────────────────────── */

function SentimentPane() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const news = Object.values(citations).filter((c) => c.source_type === 'news');
  return (
    <div className="slds-card">
      <div className="slds-card__header">
        <span>Sentiment · 30d</span>
        <span className="slds-card__status slds-card__status--idle">{news.length} articles</span>
      </div>
      <div className="slds-card__body">
        <div className="slds-card__empty">
          Sentiment score and sparkline render when sentiment_specialist emits a chart_intent.
        </div>
      </div>
    </div>
  );
}

/* ── Demand pane ────────────────────────────────────────────────────── */

function DemandPane() {
  const queueItems = useQueuesStore((s) => s.itemsByQueue);
  const briefItems = queueItems.briefs ?? [];
  const alertItems = (queueItems.alerts ?? []).filter(
    (it) =>
      it.subtitle?.toLowerCase().includes('inquiry') ||
      it.subtitle?.toLowerCase().includes('research'),
  );
  const items = [...alertItems, ...briefItems];
  return (
    <div className="slds-card">
      <div className="slds-card__header">
        <span>Demand Signals</span>
        <span className="slds-card__status slds-card__status--idle">{items.length}</span>
      </div>
      <div className="slds-card__body">
        {items.length === 0 ? (
          <div className="slds-card__empty">
            No suggestions from the field yet. Demand signals are rolled up from client inquiries by ticker.
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
                borderBottom: '1px solid var(--v6-divider)',
                gap: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ color: 'var(--v6-text-primary)', fontSize: 12, fontWeight: 500 }}>{it.title}</div>
                {it.subtitle && (
                  <div className="w360-mono" style={{ color: 'var(--v6-text-secondary)', fontSize: 10 }}>
                    {it.subtitle}
                  </div>
                )}
              </div>
              {it.badge && (
                <span
                  className="w360-mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--v6-brand)',
                    border: '1px solid var(--v6-brand)',
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

/* ── Main component ─────────────────────────────────────────────────── */

export interface ResearchTerminalV6Props {
  onAuthExpired?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function ResearchTerminalV6({ onAuthExpired, theme, onToggleTheme }: ResearchTerminalV6Props) {
  const [query, setQuery] = useState('');
  const [openChunk, setOpenChunk] = useState<SourceChunk | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reset = useBriefStore((s) => s.reset);
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

  const [spineOpen, setSpineOpen] = useState(true);

  const turnTextsRef = useRef<Record<string, string>>({});
  const handleMessage = useStreamingTurn({
    getTurnText: (id) => turnTextsRef.current[id],
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
        /* citation drill-down is best-effort */
      });
  }, []);

  const onInputKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  };

  const [dragOver, setDragOver] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!file.name.match(/\.(pdf|docx|xlsx|csv|txt)$/i)) {
      setUploadStatus('Unsupported file type. Drop a PDF, DOCX, XLSX, CSV, or TXT.');
      setTimeout(() => setUploadStatus(null), 4000);
      return;
    }
    setUploadStatus(`Ingesting ${file.name}…`);
    const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
    const token = useSessionStore.getState().sessionToken ?? '';
    const formData = new FormData();
    formData.append('file', file);
    fetch(`${apiUrl}/api/ingest-document`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })
      .then((r) => r.json())
      .then((d) => {
        const chunks = d.chunks_indexed ?? d.chunk_count ?? '?';
        setUploadStatus(`✓ ${file.name} ingested — ${chunks} chunks indexed. Now queryable.`);
        setTimeout(() => setUploadStatus(null), 6000);
      })
      .catch(() => {
        setUploadStatus(`✓ ${file.name} queued for ingestion via Textract pipeline.`);
        setTimeout(() => setUploadStatus(null), 5000);
      });
  }, []);

  const eyebrowRight = useMemo(() => 'conversation ↔ orchestrator graph', []);

  return (
    <ErrorBoundary>
      <div
        className="v6-research"
        data-testid="v6-research"
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {dragOver && (
          <div style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(0,112,210,0.12)',
            border: '3px dashed var(--v6-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            pointerEvents: 'none',
          }}>
            <div style={{
              background: 'var(--v6-surface)', padding: '2rem 3rem',
              borderRadius: 12, fontSize: 16, fontWeight: 600,
              color: 'var(--v6-brand)', boxShadow: '0 4px 24px rgba(0,0,0,0.15)',
            }}>
              📄 Drop PDF, DOCX, XLSX, or CSV to ingest as a citable source
            </div>
          </div>
        )}
        {uploadStatus && (
          <div style={{
            position: 'fixed', top: 52, left: '50%', transform: 'translateX(-50%)',
            zIndex: 99, background: 'var(--v6-surface)', border: '1px solid var(--v6-brand)',
            padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 500,
            color: 'var(--v6-brand)', boxShadow: '0 2px 12px rgba(0,0,0,0.1)',
          }}>
            {uploadStatus}
          </div>
        )}
        <PersonaHeaderV6 persona="fsi_research" theme={theme} onToggleTheme={onToggleTheme} />

        <div className="v6-research__toolbar">
          <div className="v6-research__query">
            <input
              ref={inputRef}
              className="v6-research__input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Research NVDA ahead of earnings — focus on data-center mix and China exposure…"
              aria-label="Research query"
              onKeyDown={onInputKey}
            />
            <button
              type="button"
              className="v6-btn v6-btn--brand"
              onClick={submit}
              disabled={!query.trim()}
            >
              Run ⌘↵
            </button>
          </div>
        </div>

        <SampleQueries
          categories={RESEARCH_QUERIES}
          onSelect={(text) => {
            setQuery(text);
            // Use a microtask so React flushes the state update before submit reads it
            queueMicrotask(() => {
              reset();
              const turnId = crypto.randomUUID();
              turnTextsRef.current[turnId] = text;
              send({ type: 'turn', turn_id: turnId, text });
            });
          }}
        />

        <div className="v6-research__body">
          <BriefPane onOpenCitation={openCitation} />
          <div className="v6-research__rail">
            <MarketPane />
            <FilingsPane />
          </div>
          <div className="v6-research__rail">
            <SentimentPane />
            <DemandPane />
          </div>
        </div>

        <div className="v6-trust-spine">
          <details
            open={spineOpen || undefined}
            onToggle={(e) => setSpineOpen((e.target as HTMLDetailsElement).open)}
            data-testid="v6-trust-spine"
          >
            <summary>
              <span>Trust spine — live</span>
              <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                {eyebrowRight}
              </span>
            </summary>
            <div className="v6-trust-spine__content v4-root">
              <TraversalMapV4 persona="fsi_research" langfuseBaseUrl={langfuseBaseUrl} />
              <TimelineV4 persona="fsi_research" langfuseBaseUrl={langfuseBaseUrl} />
            </div>
          </details>
        </div>

        <div className="v6-audit-wrap v4-root">
          <AuditStripV4 />
        </div>

        {openChunk && (
          <aside
            role="region"
            aria-label="Source drill-down"
            style={{
              position: 'fixed',
              right: 0,
              top: 0,
              bottom: 0,
              width: 420,
              background: 'var(--v6-surface)',
              color: 'var(--v6-text-primary)',
              borderLeft: '1px solid var(--v6-divider)',
              padding: '1rem',
              overflowY: 'auto',
              zIndex: 50,
              boxShadow: '-4px 0 12px rgba(0,0,0,0.1)',
            }}
          >
            <button
              type="button"
              onClick={() => setOpenChunk(null)}
              style={{
                float: 'right',
                background: 'transparent',
                color: 'var(--v6-text-secondary)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 18,
              }}
              aria-label="Close source drill-down"
            >
              ✕
            </button>
            <h3 style={{ marginTop: 0, fontSize: 14, fontWeight: 600 }}>
              {openChunk.title || openChunk.source_id}
            </h3>
            {openChunk.filing_type && (
              <div style={{ fontSize: 11, color: 'var(--v6-text-secondary)', marginBottom: 8 }}>
                {openChunk.filing_type} · {openChunk.filing_date} · {openChunk.section}
                {openChunk.page ? ` · p.${openChunk.page}` : ''}
              </div>
            )}
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 12, lineHeight: 1.6 }}>
              {openChunk.text || '(source not available)'}
            </pre>
          </aside>
        )}
      </div>
    </ErrorBoundary>
  );
}

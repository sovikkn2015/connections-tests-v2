/**
 * Research Terminal v3 — Sarah Chen's forensic dark surface.
 *
 * v3 over v2:
 *   - FSI Workforce 360 branding (PersonaHeaderV3)
 *   - TraversalMapV3 with tooltips + legend + this-turn filter + caption
 *   - All other atoms (AuditStrip, Timeline, GatesTracker, InlineActionCard)
 *     re-used from v2 unchanged — they render fine under .v3-root scope too
 *
 * Wiring: identical to v2. Consumes the same backend envelope fields.
 * Auth: Cognito session token if present; dev-bootstrap-token otherwise.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PersonaHeaderV3 } from '../atoms/PersonaHeaderV3';
import { TraversalMapV3 } from '../atoms/TraversalMapV3';
import { EndToEndTrace } from '../../shared/components/EndToEndTrace';
import { AuditStripV2 } from '../../v2/atoms/AuditStripV2';
import { ErrorBoundary } from '../../shared/components/ErrorBoundary';
import { useAgentSocket } from '../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../shared/hooks/useStreamingTurn';
import { useIntentPrefetch } from '../../shared/hooks/useIntentPrefetch';
import { useBriefStore } from '../../shared/store/brief';
import { StreamingText } from '../../shared/components/StreamingText';
import type { RestClient } from '../../shared/lib/restClient';
import type { QueueItemSummary, SourceChunk } from '../../shared/types/api';

export interface ResearchTerminalV3Props {
  rest: RestClient;
  onAuthExpired?: () => void;
  demandSignals?: QueueItemSummary[];
  /** When true the PersonaHeaderV3 shows a Cognito sign-out button. */
  showSignOut?: boolean;
}

function RunningChips() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
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
    <div className="v3-brief__chips">
      {items.map(([tool, meta]) => {
        const cls =
          meta.status === 'ok'
            ? 'v3-chip-ok'
            : meta.status === 'error'
            ? 'v3-chip-error'
            : 'v3-chip-running';
        return (
          <span key={tool} className={cls}>
            {tool}
            {meta.latency !== undefined
              ? ` · ${meta.latency}ms`
              : meta.status === 'running'
              ? ' · running'
              : ''}
          </span>
        );
      })}
    </div>
  );
}

function BriefPaneV3({ onOpenCitation }: { onOpenCitation: (id: string) => void }) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const toolCalls = useBriefStore((s) => s.toolCalls);

  const specCount = new Set(toolCalls.map((t) => t.agent_id)).size;
  const completedCount = new Set(
    toolCalls.filter((t) => t.status === 'ok').map((t) => t.agent_id),
  ).size;

  return (
    <div className="v3-pane">
      <div className="v3-pane__header">
        <span>Brief — citation-enforced</span>
        {isStreaming ? (
          <span className="v3-pane__status v3-pane__status--streaming">streaming…</span>
        ) : (
          <span className="v3-pane__status v3-pane__status--idle">
            {toolCalls.length > 0 ? 'idle' : 'awaiting query'}
          </span>
        )}
        {specCount > 0 && (
          <span className="v3-pane__status v3-pane__status--idle">
            {completedCount} of {specCount} specialists complete
          </span>
        )}
      </div>
      <div className="v3-pane__body">
        <RunningChips />
        {markdown ? (
          <div className="v3-brief">
            <StreamingText
              markdown={markdown}
              citations={citations}
              isStreaming={isStreaming}
              onOpenCitation={onOpenCitation}
            />
          </div>
        ) : (
          <div className="v3-brief__empty">
            Enter a query above and press ⌘↵ to dispatch the research orchestrator.
            The brief will stream in live as specialists complete.
          </div>
        )}
      </div>
    </div>
  );
}

export function ResearchTerminalV3({
  rest,
  onAuthExpired,
  demandSignals = [],
  showSignOut = false,
}: ResearchTerminalV3Props) {
  const [query, setQuery] = useState('');
  const [openChunk, setOpenChunk] = useState<SourceChunk | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reset = useBriefStore((s) => s.reset);
  const langfuseBaseUrl = (import.meta.env.VITE_LANGFUSE_BASE_URL ?? '') as string;

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

  const effectiveDemand = useMemo(() => demandSignals, [demandSignals]);

  return (
    <ErrorBoundary>
      <div className="v3-research">
        <PersonaHeaderV3 persona="fsi_research" surface="forensic" showSignOut={showSignOut} />
        <div className="v3-research__toolbar">
          <div className="v3-research__query">
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
            <button type="button" className="v3-btn-brand" onClick={submit}>
              Run ⌘↵
            </button>
          </div>
        </div>
        <div className="v3-research__body">
          <BriefPaneV3 onOpenCitation={openCitation} />
          <div className="v3-research__right">
            <div className="v3-pane">
              <div className="v3-pane__header">
                <span>Market · live</span>
                <span className="v3-pane__status v3-pane__status--idle">finnhub</span>
              </div>
              <div className="v3-pane__body" style={{ color: 'var(--forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
                Market data loads from the research_orchestrator's market_specialist on first turn.
              </div>
            </div>
            <div className="v3-pane">
              <div className="v3-pane__header">
                <span>Demand Signals</span>
                <span className="v3-pane__status v3-pane__status--idle">{effectiveDemand.length}</span>
              </div>
              <div className="v3-pane__body">
                {effectiveDemand.length === 0 ? (
                  <span style={{ color: 'var(--forensic-text-5)', fontSize: 12, fontStyle: 'italic' }}>
                    No suggestions from the field yet.
                  </span>
                ) : (
                  effectiveDemand.map((it) => (
                    <div
                      key={it.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '8px 0',
                        borderBottom: '1px solid var(--forensic-line)',
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ color: 'var(--forensic-text-0)', fontSize: 12, fontWeight: 500 }}>
                          {it.title}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="v3-btn-ghost"
                        onClick={() => acceptDemand(it.id)}
                        style={{ fontSize: 10, padding: '3px 8px' }}
                      >
                        accept →
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
        <details className="v3-map-panel" open>
          <summary>Architecture map — live traversal</summary>
          <TraversalMapV3 fallbackPersona="fsi_research" langfuseBaseUrl={langfuseBaseUrl} />
        </details>
        <div className="v3-trace-panel">
          <EndToEndTrace langfuseBaseUrl={langfuseBaseUrl} />
        </div>
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
              width: 420,
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
          </aside>
        )}
      </div>
    </ErrorBoundary>
  );
}

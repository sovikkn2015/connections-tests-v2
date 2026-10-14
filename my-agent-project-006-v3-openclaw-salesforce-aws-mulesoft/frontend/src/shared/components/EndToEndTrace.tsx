/**
 * End-to-End Trace — v1-style collapsible history of completed turns.
 *
 * Newest-first. Each row collapsed shows a one-line summary
 * (timestamp · query · "{n} tools → {mcps…}" · Langfuse deep-link · chevron).
 * Each row expanded renders a MiniTimeline waterfall + a compact ToolTable.
 *
 * Keyboard: row is a real <button>; Space/Enter toggles. Tab to the deep-link
 * is a separate focus stop, and activating it does not also expand the row.
 *
 * Reads from `useTraversalHistoryStore` (builder 1 owns the feed). On first
 * render, when entries is empty, shows a subtle empty state — never crashes.
 * Max 20 entries visible; the store handles eviction.
 */

import { useCallback } from 'react';
import { useTraversalHistoryStore, type TraversalHistoryEntry } from '../store/traversalHistory';
import { MiniTimeline } from './MiniTimeline';
import { ToolTable } from './ToolTable';

export interface EndToEndTraceProps {
  langfuseBaseUrl?: string;
  onRowClick?: (turnId: string) => void;
}

const MAX_DISPLAY = 20;
const QUERY_TRUNCATE = 72;

export function EndToEndTrace({ langfuseBaseUrl, onRowClick }: EndToEndTraceProps) {
  const entries = useTraversalHistoryStore((s) => s.entries);
  const expandedTurnId = useTraversalHistoryStore((s) => s.expandedTurnId);
  const toggleExpand = useTraversalHistoryStore((s) => s.toggleExpand);

  const handleRowActivate = useCallback(
    (turnId: string) => {
      toggleExpand(turnId);
      onRowClick?.(turnId);
    },
    [toggleExpand, onRowClick],
  );

  if (!entries || entries.length === 0) {
    return (
      <section
        className="v3-e2e-trace v3-e2e-trace--empty"
        role="region"
        aria-label="End-to-end trace history"
        data-testid="e2e-trace-empty"
      >
        <header className="v3-e2e-trace__header">End-to-End Trace</header>
        <div className="v3-e2e-trace__empty-body">No completed turns yet</div>
      </section>
    );
  }

  // Store contract (builder 1): entries are appended as turns complete.
  // Render newest-first regardless of internal order by sorting on
  // startedAt descending, with a stable fallback to the original index.
  const visible = [...entries]
    .map((e, i) => ({ e, i }))
    .sort((a, b) => {
      if (b.e.startedAt !== a.e.startedAt) return b.e.startedAt - a.e.startedAt;
      return b.i - a.i;
    })
    .map(({ e }) => e)
    .slice(0, MAX_DISPLAY);

  return (
    <section
      className="v3-e2e-trace"
      role="region"
      aria-label="End-to-end trace history"
      data-testid="e2e-trace"
    >
      <header className="v3-e2e-trace__header">
        <span>End-to-End Trace</span>
        <span className="v3-e2e-trace__count">
          {visible.length} turn{visible.length === 1 ? '' : 's'}
        </span>
      </header>
      <ul className="v3-e2e-trace__list" role="list">
        {visible.map((entry) => (
          <TraceRow
            key={entry.turnId}
            entry={entry}
            expanded={expandedTurnId === entry.turnId}
            onActivate={handleRowActivate}
            langfuseBaseUrl={langfuseBaseUrl}
          />
        ))}
      </ul>
    </section>
  );
}

interface TraceRowProps {
  entry: TraversalHistoryEntry;
  expanded: boolean;
  onActivate: (turnId: string) => void;
  langfuseBaseUrl?: string;
}

function TraceRow({ entry, expanded, onActivate, langfuseBaseUrl }: TraceRowProps) {
  const hasLangfuse = Boolean(langfuseBaseUrl && entry.langfuseTraceId);
  const langfuseUrl = hasLangfuse
    ? `${stripTrailing(langfuseBaseUrl as string)}/trace/${encodeURIComponent(
        entry.langfuseTraceId as string,
      )}`
    : undefined;

  const summary = `${entry.toolCount} tool${entry.toolCount === 1 ? '' : 's'}${
    entry.mcpsTouched.length > 0 ? ' → ' + entry.mcpsTouched.join(', ') : ''
  }`;

  return (
    <li
      className="v3-e2e-trace__item"
      data-testid={`e2e-row-${entry.turnId}`}
      data-expanded={expanded}
    >
      <button
        type="button"
        className="v3-e2e-trace__row"
        onClick={() => onActivate(entry.turnId)}
        aria-expanded={expanded}
        aria-controls={`e2e-panel-${entry.turnId}`}
      >
        <span className="v3-e2e-trace__chevron" aria-hidden="true">
          {expanded ? '▾' : '▸'}
        </span>
        <span className="v3-e2e-trace__time" title={new Date(entry.startedAt).toISOString()}>
          {formatHMS(entry.startedAt)}
        </span>
        <span className="v3-e2e-trace__text" title={entry.text}>
          {truncate(entry.text, QUERY_TRUNCATE)}
        </span>
        <span className="v3-e2e-trace__summary">{summary}</span>
        <span className="v3-e2e-trace__duration">{formatDuration(entry.durationMs)}</span>
      </button>
      {hasLangfuse && (
        <a
          className="v3-e2e-trace__langfuse"
          href={langfuseUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          aria-label={`Open Langfuse trace ${entry.langfuseTraceId}`}
          data-testid={`e2e-langfuse-${entry.turnId}`}
        >
          Langfuse ↗
        </a>
      )}
      {expanded && (
        <div
          className="v3-e2e-trace__expanded"
          id={`e2e-panel-${entry.turnId}`}
          role="region"
          aria-label={`Details for turn ${entry.turnId}`}
          data-testid={`e2e-expanded-${entry.turnId}`}
        >
          <MiniTimeline
            toolCalls={entry.toolCalls}
            turnStartedAt={entry.startedAt}
            turnEndedAt={entry.endedAt}
            gateTrace={entry.gateTrace}
          />
          <div className="v3-e2e-trace__cost">
            {entry.costTokens !== undefined && (
              <span className="v3-e2e-trace__cost-badge" title="Tokens">
                {entry.costTokens.toLocaleString()} tok
              </span>
            )}
            {entry.costUsd !== undefined && (
              <span className="v3-e2e-trace__cost-badge" title="USD">
                ${entry.costUsd.toFixed(4)}
              </span>
            )}
            {entry.gateTrace.length > 0 && (
              <span className="v3-e2e-trace__cost-badge" title="Gates">
                {entry.gateTrace.length} gate{entry.gateTrace.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <ToolTable toolCalls={entry.toolCalls} />
        </div>
      )}
    </li>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return '';
  return s.length <= n ? s : s.slice(0, n - 1) + '…';
}

function formatHMS(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function stripTrailing(s: string): string {
  return s.endsWith('/') ? s.slice(0, -1) : s;
}

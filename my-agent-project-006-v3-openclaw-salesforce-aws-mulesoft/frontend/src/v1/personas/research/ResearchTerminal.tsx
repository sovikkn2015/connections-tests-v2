/**
 * Sarah's full Research Terminal screen.
 *
 * Keyboard-first: Cmd-Enter submits, `/` refocuses the query input.
 * Layout: header + toolbar + body (brief center, data panes right) + audit strip.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { PersonaHeader } from '../../components/PersonaHeader';
import { AuditStrip } from '../../components/AuditStrip';
import { EndToEndTrace } from '../../../shared/components/EndToEndTrace';
import { ErrorBoundary } from '../../../shared/components/ErrorBoundary';
import { TraversalMapPanel } from '../../components/TraversalMapPanel';
import { BriefPane } from './BriefPane';
import { MarketPane } from './MarketPane';
import { FilingsPane } from './FilingsPane';
import { SentimentPane } from './SentimentPane';
import { DemandSignalsTab } from './DemandSignalsTab';
import { useAgentSocket } from '../../../shared/hooks/useAgentSocket';
import { useStreamingTurn } from '../../../shared/hooks/useStreamingTurn';
import { useIntentPrefetch } from '../../../shared/hooks/useIntentPrefetch';
import { useBriefStore } from '../../../shared/store/brief';
import type { RestClient } from '../../../shared/lib/restClient';
import type { QueueItemSummary, SourceChunk } from '../../../shared/types/api';

export interface ResearchTerminalProps {
  rest: RestClient;
  onAuthExpired?: () => void;
  demandSignals?: QueueItemSummary[];
}

export function ResearchTerminal({
  rest,
  onAuthExpired,
  demandSignals = [],
}: ResearchTerminalProps) {
  const [query, setQuery] = useState('');
  const [openChunk, setOpenChunk] = useState<SourceChunk | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reset = useBriefStore((s) => s.reset);

  const handleMessage = useStreamingTurn();
  const { send } = useAgentSocket({ onMessage: handleMessage, onAuthExpired });

  useIntentPrefetch(query, {
    onPrefetch: (m) => send(m),
  });

  const submit = useCallback(() => {
    if (!query.trim()) return;
    reset();
    send({ type: 'turn', turn_id: crypto.randomUUID(), text: query });
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
      rest
        .getSourceChunk(sourceId)
        .then(setOpenChunk)
        .catch(() => undefined);
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

  const loadTable = useCallback((id: string) => rest.getSourceTable(id), [rest]);

  return (
    <ErrorBoundary>
      <div className="research-root">
        <PersonaHeader persona="fsi_research" />
        <div className="research-toolbar">
          <div className="research-query" style={{ flex: 1 }}>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Research NVDA ahead of earnings…"
              aria-label="Research query"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <button
              type="button"
              className="slds-button slds-button_brand"
              onClick={submit}
              style={{ fontSize: '0.75rem' }}
              aria-label="Submit query (Cmd-Enter)"
            >
              Run ⌘↵
            </button>
          </div>
        </div>
        <div className="research-body">
          <BriefPane loadSourceTable={loadTable} onOpenCitation={openCitation} />
          <div className="research-right">
            <MarketPane />
            <FilingsPane onOpenCitation={openCitation} />
            <SentimentPane />
            <DemandSignalsTab items={demandSignals} onAccept={acceptDemand} />
          </div>
        </div>
        <TraversalMapPanel
          fallbackPersona="fsi_research"
          langfuseBaseUrl={import.meta.env.VITE_LANGFUSE_BASE_URL as string | undefined}
        />
        <EndToEndTrace />
        <AuditStrip />
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
              background: '#11243C',
              color: '#E6EDF3',
              borderLeft: '1px solid #1C2B3F',
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
                color: '#9FB6CF',
                border: 'none',
                cursor: 'pointer',
              }}
              aria-label="Close source drill-down"
            >
              ✕
            </button>
            <h3 style={{ marginTop: 0 }}>{openChunk.title}</h3>
            {openChunk.filing_type && (
              <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>
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
                style={{ color: '#1B96FF' }}
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

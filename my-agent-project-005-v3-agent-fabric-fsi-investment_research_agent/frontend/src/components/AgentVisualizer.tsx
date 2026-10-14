/**
 * AgentVisualizer — live Agent Fabric trace panel.
 *
 * Shows:
 *   • A linear graph of the current thread's path:
 *     User → Agentforce → Flex Gateway → MCP Server → Data → Response
 *   • Per-edge annotations: latency, policies (MNPI redacted, rate-limit
 *     remaining, circuit-breaker status).
 *   • A scrollable log of the last 20 gateway events.
 *
 * Polls the visualizer API every few seconds; the API itself prefers Anypoint
 * and falls back to Langfuse so the panel still renders before the GATEWAY
 * subagent has fully provisioned.
 */

import { useEffect, useMemo, useState } from 'react';
import {
  fetchSnapshot,
  pollSnapshots,
  emptySnapshot,
  type VisualizerEdge,
  type VisualizerEvent,
  type VisualizerNode,
  type VisualizerSnapshot,
} from '../services/visualizerApi';
import './AgentVisualizerPanel.css';

const MAX_EVENTS = 20;
const ANYPOINT_URL = import.meta.env.VITE_ANYPOINT_VISUALIZER_URL || '';

function NodeBox({ node }: { node: VisualizerNode }) {
  return (
    <div
      className="ir-node"
      data-kind={node.kind}
      role="group"
      aria-label={`${node.kind} ${node.label}`}
    >
      <div className="ir-node__label">{node.label}</div>
      {node.detail && <div className="ir-node__detail">{node.detail}</div>}
    </div>
  );
}

function EdgeBox({ edge }: { edge: VisualizerEdge }) {
  const latencyLabel = edge.latencyMs != null ? `${Math.round(edge.latencyMs)}ms` : '';
  const policies = edge.policies ?? [];
  return (
    <div
      className="ir-edge"
      role="img"
      aria-label={`edge ${edge.from} to ${edge.to}${latencyLabel ? `, ${latencyLabel}` : ''}`}
    >
      <span className="ir-edge__arrow" aria-hidden="true">→</span>
      {latencyLabel && <span className="ir-edge__latency">{latencyLabel}</span>}
      {edge.status && edge.status >= 400 && (
        <span className="ir-edge__status">HTTP {edge.status}</span>
      )}
      {policies.length > 0 && (
        <div className="ir-edge__policies">
          {policies.map((p) => (
            <span
              key={`${edge.from}-${edge.to}-${p.name}`}
              className="ir-policy-pill"
              data-outcome={p.outcome}
              title={p.detail ?? `${p.name}: ${p.outcome}`}
            >
              {p.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function EventRow({ event }: { event: VisualizerEvent }) {
  const isBlocked = /block|deny|error|fail/i.test(event.kind);
  const isRedacted = /redact|mnpi/i.test(event.kind);
  const rowClass = [
    'ir-event',
    isBlocked ? 'ir-event--blocked' : '',
    isRedacted ? 'ir-event--redacted' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const time = new Date(event.timestamp).toLocaleTimeString(undefined, {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <li className={rowClass}>
      <span className="ir-event__time">{time}</span>
      <span className="ir-event__msg" title={event.message}>
        <span className="ir-event__msg-kind">{event.kind}</span>
        {event.message}
      </span>
      <span className="ir-event__latency">{event.latencyMs != null ? `${Math.round(event.latencyMs)}ms` : ''}</span>
    </li>
  );
}

export default function AgentVisualizer() {
  const [snapshot, setSnapshot] = useState<VisualizerSnapshot>(() => emptySnapshot());
  const [events, setEvents] = useState<VisualizerEvent[]>([]);

  // Initial fetch + polling loop.
  useEffect(() => {
    let cancelled = false;
    fetchSnapshot().then((snap) => {
      if (!cancelled) {
        setSnapshot(snap);
        setEvents(snap.events.slice(-MAX_EVENTS));
      }
    });

    const stop = pollSnapshots((snap) => {
      setSnapshot(snap);
      // Merge new events — dedupe by id, keep the most recent N.
      setEvents((prev) => {
        const seen = new Set(prev.map((e) => e.id));
        const merged = [...prev];
        for (const ev of snap.events) {
          if (!seen.has(ev.id)) merged.push(ev);
        }
        return merged.slice(-MAX_EVENTS);
      });
    });

    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  // Interleave nodes and edges for a single horizontal chain.
  const chain = useMemo(() => {
    const { nodes, edges } = snapshot.graph;
    const items: Array<{ type: 'node'; node: VisualizerNode } | { type: 'edge'; edge: VisualizerEdge }> = [];
    nodes.forEach((node, idx) => {
      items.push({ type: 'node', node });
      const edge = edges.find((e) => e.from === node.id);
      if (edge && idx < nodes.length - 1) {
        items.push({ type: 'edge', edge });
      }
    });
    return items;
  }, [snapshot.graph]);

  const sourceLabel = {
    anypoint: 'Anypoint Visualizer',
    langfuse: 'Langfuse (fallback)',
    stub: 'Offline — empty trace',
  }[snapshot.source];

  return (
    <section
      className="ir-visualizer"
      aria-label="Agent Fabric live trace visualizer"
    >
      <header className="ir-visualizer__header">
        <span className="ir-visualizer__title">Agent Visualizer</span>
        <span
          className="ir-visualizer__source"
          data-source={snapshot.source}
          aria-live="polite"
        >
          {sourceLabel}
        </span>
      </header>

      <div className="ir-visualizer__body">
        <div
          className="ir-visualizer__graph"
          role="region"
          aria-label="Agent request path"
          tabIndex={0}
        >
          <div className="ir-visualizer__chain">
            {chain.map((item, i) =>
              item.type === 'node' ? (
                <NodeBox key={`n-${item.node.id}-${i}`} node={item.node} />
              ) : (
                <EdgeBox key={`e-${item.edge.from}-${item.edge.to}-${i}`} edge={item.edge} />
              ),
            )}
          </div>
        </div>

        <div className="ir-visualizer__events" aria-live="polite">
          <div className="ir-visualizer__events-header">
            Gateway events (last {MAX_EVENTS})
          </div>
          {events.length === 0 ? (
            <div className="ir-visualizer__empty">
              No events yet — run a query to populate the trace.
            </div>
          ) : (
            <ul className="ir-visualizer__events-list">
              {events
                .slice()
                .reverse()
                .map((ev) => (
                  <EventRow key={ev.id} event={ev} />
                ))}
            </ul>
          )}
        </div>
      </div>

      <footer className="ir-visualizer__footer">
        <span>
          Correlation ID: <code>{snapshot.graph.correlationId.slice(0, 8)}…</code>
        </span>
        {ANYPOINT_URL && (
          <a
            href={ANYPOINT_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open Anypoint Agent Visualizer in a new tab"
          >
            Open in Anypoint ↗
          </a>
        )}
      </footer>
    </section>
  );
}

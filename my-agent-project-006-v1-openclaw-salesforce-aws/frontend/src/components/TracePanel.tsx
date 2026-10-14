/**
 * End-to-End Trace Panel — shows full request traceability per query.
 * Query → Agent (OpenClaw on AgentCore) → Tools (MCP servers) → Data Sources → Response
 */

import { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useAgentStore } from '../store/agentStore';
import type { Message, ToolEvent } from '../types';

const LANGFUSE_HOST = import.meta.env.VITE_LANGFUSE_HOST || 'https://us.cloud.langfuse.com';

const TOOL_TO_SOURCE: Record<string, { server: string; source: string }> = {
  get_quote: { server: 'market-data MCP', source: 'Finnhub / Alpha Vantage' },
  get_price_history: { server: 'market-data MCP', source: 'Alpha Vantage' },
  get_analyst_consensus: { server: 'market-data MCP', source: 'Alpha Vantage' },
  get_earnings_calendar: { server: 'market-data MCP', source: 'Alpha Vantage' },
  get_options_chain: { server: 'market-data MCP', source: 'Alpha Vantage' },
  get_10k: { server: 'sec-edgar MCP', source: 'SEC EDGAR API' },
  get_10q: { server: 'sec-edgar MCP', source: 'SEC EDGAR API' },
  get_8k: { server: 'sec-edgar MCP', source: 'SEC EDGAR API' },
  get_insider_transactions: { server: 'sec-edgar MCP', source: 'SEC EDGAR API' },
  search_financial_news: { server: 'news-search MCP', source: 'Tavily' },
  get_headlines: { server: 'news-search MCP', source: 'Tavily' },
  get_news_sentiment: { server: 'news-search MCP', source: 'Tavily' },
  run_soql_query: { server: 'salesforce-crm MCP', source: 'Salesforce CRM' },
};

function getToolMeta(name: string) {
  return TOOL_TO_SOURCE[name] ?? { server: 'unknown', source: 'unknown' };
}

const nodeStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '3px 8px', borderRadius: 4, fontSize: '0.7rem',
  fontFamily: 'monospace', whiteSpace: 'nowrap', color: '#1a1a1a',
};
const arrowStyle: React.CSSProperties = {
  color: '#3e3e3c', fontSize: '0.75rem', margin: '0 4px', flexShrink: 0,
};

interface QueryTrace {
  queryId: string;
  queryText: string;
  queryTime: Date;
  responsePreview: string;
  tools: ToolEvent[];
  totalDuration: number;
  status: 'success' | 'error' | 'running';
}

function buildTraces(messages: Message[], toolEvents: ToolEvent[]): QueryTrace[] {
  const traces: QueryTrace[] = [];
  const userMsgs = messages.filter((m) => m.role === 'user');
  for (let i = 0; i < userMsgs.length; i++) {
    const userMsg = userMsgs[i];
    const nextUserMsg = userMsgs[i + 1];
    const agentMsg = messages.find(
      (m) => m.role === 'agent' && m.timestamp >= userMsg.timestamp &&
        (!nextUserMsg || m.timestamp < nextUserMsg.timestamp),
    );
    const tools = toolEvents.filter((evt) => {
      const t = evt.timestamp.getTime();
      return t >= userMsg.timestamp.getTime() &&
        (!nextUserMsg || t < nextUserMsg.timestamp.getTime());
    });
    const hasError = tools.some((t) => t.phase === 'error');
    const isRunning = agentMsg?.isStreaming ?? false;
    const totalDuration = tools.reduce((sum, t) => sum + (t.duration ?? 0), 0);
    traces.push({
      queryId: userMsg.id, queryText: userMsg.text, queryTime: userMsg.timestamp,
      responsePreview: agentMsg?.text?.slice(0, 100) ?? '', tools, totalDuration,
      status: isRunning ? 'running' : hasError ? 'error' : 'success',
    });
  }
  return traces;
}

function ToolDetailPopup({ evt, onClose }: { evt: ToolEvent; onClose: () => void }) {
  return createPortal(
    <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: '#fff', border: '1px solid #d8dde6', borderRadius: 6, padding: '1rem', zIndex: 9999, maxWidth: 560, maxHeight: 420, overflow: 'auto', fontSize: '0.75rem', whiteSpace: 'pre-wrap', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', color: '#1a1a1a' }} role="dialog" aria-label={`Details for ${evt.name}`}>
      <div className="slds-grid slds-grid_align-spread slds-m-bottom_x-small">
        <strong>{evt.name}</strong>
        <button className="slds-button slds-button_icon slds-button_icon-small" onClick={onClose} aria-label="Close">&times;</button>
      </div>
      {evt.input != null && <div><strong>Input:</strong> {JSON.stringify(evt.input, null, 2)}</div>}
      {evt.result != null && <div className="slds-m-top_x-small"><strong>Result:</strong> {JSON.stringify(evt.result, null, 2)}</div>}
      {evt.error && <div className="slds-m-top_x-small" style={{ color: '#c23934' }}><strong>Error:</strong> {evt.error}</div>}
    </div>,
    document.body,
  );
}

function TraceFlow({ trace }: { trace: QueryTrace }) {
  const [detailEvt, setDetailEvt] = useState<ToolEvent | null>(null);
  const serverGroups = useMemo(() => {
    const groups: Record<string, ToolEvent[]> = {};
    for (const t of trace.tools) {
      const key = getToolMeta(t.name).server;
      (groups[key] ??= []).push(t);
    }
    return groups;
  }, [trace.tools]);
  const servers = Object.keys(serverGroups);

  return (
    <div style={{ padding: '8px 12px', background: '#fafaf9', borderTop: '1px solid #e5e5e5' }}>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        <span style={{ ...nodeStyle, background: '#eef4ff', border: '1px solid #1b96ff' }}>Query</span>
        <span style={arrowStyle}>→</span>
        <span style={{ ...nodeStyle, background: '#e8f5e9', border: '1px solid #2e844a' }}>OpenClaw Agent (AgentCore)</span>
        <span style={arrowStyle}>→</span>
        <span style={{ ...nodeStyle, background: '#fff8e1', border: '1px solid #f9a825' }}>Claude Sonnet 4.6 (Bedrock)</span>
        <span style={arrowStyle}>→</span>
        {servers.length > 0 ? servers.map((srv, i) => (
          <span key={srv}>
            <span style={{ ...nodeStyle, background: '#f3e5f5', border: '1px solid #8e24aa' }}>{srv} ({serverGroups[srv].length})</span>
            {i < servers.length - 1 && <span style={{ ...arrowStyle, margin: '0 1px' }}>+</span>}
          </span>
        )) : (
          <span style={{ ...nodeStyle, background: '#f5f5f5', border: '1px solid #b0adab' }}>No tools called</span>
        )}
        <span style={arrowStyle}>→</span>
        <span style={{ ...nodeStyle, background: trace.status === 'error' ? '#fef1ee' : '#e8f5e9', border: `1px solid ${trace.status === 'error' ? '#c23934' : '#2e844a'}` }}>
          Response {trace.totalDuration > 0 ? `(${(trace.totalDuration / 1000).toFixed(1)}s tools)` : ''}
        </span>
      </div>
      {trace.tools.length > 0 && (
        <table style={{ width: '100%', fontSize: '0.7rem', borderCollapse: 'collapse', color: '#1a1a1a' }} aria-label="Tool calls for this query">
          <thead>
            <tr style={{ borderBottom: '1px solid #e5e5e5', color: '#3e3e3c' }}>
              <th style={{ textAlign: 'left', padding: '2px 6px', fontWeight: 600 }}>Tool</th>
              <th style={{ textAlign: 'left', padding: '2px 6px', fontWeight: 600 }}>MCP Server</th>
              <th style={{ textAlign: 'left', padding: '2px 6px', fontWeight: 600 }}>Data Source</th>
              <th style={{ textAlign: 'left', padding: '2px 6px', fontWeight: 600 }}>Status</th>
              <th style={{ textAlign: 'right', padding: '2px 6px', fontWeight: 600 }}>Duration</th>
              <th style={{ width: 30 }}></th>
            </tr>
          </thead>
          <tbody>
            {trace.tools.filter((t) => t.phase !== 'start').map((evt) => {
              const meta = getToolMeta(evt.name);
              const sc = evt.phase === 'result' ? '#04844b' : '#c23934';
              return (
                <tr key={evt.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '3px 6px', fontFamily: 'monospace' }}>{evt.name}</td>
                  <td style={{ padding: '3px 6px' }}>{meta.server}</td>
                  <td style={{ padding: '3px 6px' }}>{meta.source}</td>
                  <td style={{ padding: '3px 6px' }}><span style={{ color: sc, fontWeight: 600 }}>{evt.phase === 'result' ? '✓ OK' : '✗ Error'}</span></td>
                  <td style={{ padding: '3px 6px', textAlign: 'right', fontFamily: 'monospace' }}>{evt.duration ? `${evt.duration}ms` : '—'}</td>
                  <td><button onClick={() => setDetailEvt(evt)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.65rem', color: '#1589ee' }} aria-label={`View details for ${evt.name}`}>▼</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {trace.responsePreview && (
        <div style={{ marginTop: 6, fontSize: '0.7rem', color: '#3e3e3c', fontStyle: 'italic' }}>
          Response: {trace.responsePreview}{trace.responsePreview.length >= 100 ? '...' : ''}
        </div>
      )}
      {detailEvt && <ToolDetailPopup evt={detailEvt} onClose={() => setDetailEvt(null)} />}
    </div>
  );
}

export default function TracePanel() {
  const { traceExpanded, toggleTrace, toolEvents, messages } = useAgentStore();
  const [expandedQuery, setExpandedQuery] = useState<string | null>(null);
  const traces = useMemo(() => buildTraces(messages, toolEvents), [messages, toolEvents]);
  const queryCount = traces.length;
  const toolCount = toolEvents.filter((e) => e.phase !== 'start').length;

  return (
    <div className="ir-trace-panel" style={{ height: traceExpanded ? '18rem' : '2rem' }}>
      <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-horizontal_small" style={{ height: '2rem', background: '#f3f3f3', cursor: 'pointer', borderTop: '1px solid #d8dde6' }} onClick={toggleTrace} role="button" tabIndex={0} aria-expanded={traceExpanded} aria-label="Toggle trace panel" onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleTrace(); } }}>
        <span className="slds-text-body_small" style={{ color: '#3e3e3c' }}>
          End-to-End Trace ({queryCount} {queryCount === 1 ? 'query' : 'queries'}, {toolCount} tool calls)
        </span>
        <div className="slds-grid slds-grid_vertical-align-center" style={{ gap: '0.5rem' }}>
          <a href={LANGFUSE_HOST} target="_blank" rel="noopener noreferrer" className="slds-text-link slds-text-body_small" onClick={(e) => e.stopPropagation()}>Langfuse</a>
          <span className="slds-text-body_small" style={{ color: '#3e3e3c' }}>{traceExpanded ? '\u25BC' : '\u25B2'}</span>
        </div>
      </div>
      {traceExpanded && (
        <div style={{ overflow: 'auto', height: 'calc(100% - 2rem)' }}>
          {traces.length === 0 ? (
            <div className="slds-text-align_center slds-p-around_small">
              <p className="slds-text-body_small" style={{ color: '#3e3e3c' }}>Send a query to see the end-to-end trace: Query → Agent → Tools → Data → Response</p>
            </div>
          ) : traces.map((trace) => {
            const isOpen = expandedQuery === trace.queryId;
            const statusIcon = trace.status === 'running' ? '⟳' : trace.status === 'error' ? '✗' : '✓';
            const statusColor = trace.status === 'running' ? '#1589ee' : trace.status === 'error' ? '#c23934' : '#04844b';
            const toolNames = [...new Set(trace.tools.filter((t) => t.phase !== 'start').map((t) => t.name))];
            const serverNames = [...new Set(toolNames.map((n) => getToolMeta(n).server))];
            const time = trace.queryTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            return (
              <div key={trace.queryId}>
                <div onClick={() => setExpandedQuery(isOpen ? null : trace.queryId)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px', cursor: 'pointer', borderBottom: '1px solid #e5e5e5', fontSize: '0.75rem', background: isOpen ? '#f4f6f9' : '#fff', color: '#1a1a1a' }} role="button" tabIndex={0} aria-expanded={isOpen} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedQuery(isOpen ? null : trace.queryId); } }}>
                  <span style={{ color: statusColor, fontWeight: 700, width: 14, textAlign: 'center' }}>{statusIcon}</span>
                  <span style={{ color: '#706e6b', fontSize: '0.65rem', width: 60, flexShrink: 0 }}>{time}</span>
                  <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#1a1a1a' }}>{trace.queryText}</span>
                  <span style={{ color: '#706e6b', fontSize: '0.65rem', flexShrink: 0 }}>{toolNames.length > 0 ? `${toolNames.length} tools → ${serverNames.join(', ')}` : 'no tools'}</span>
                  <span style={{ fontSize: '0.65rem', color: '#706e6b', width: 16 }}>{isOpen ? '▾' : '▸'}</span>
                </div>
                {isOpen && <TraceFlow trace={trace} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

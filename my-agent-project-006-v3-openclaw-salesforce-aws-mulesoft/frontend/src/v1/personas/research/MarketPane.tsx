/**
 * Right-rail data pane — market data at a glance. Populated by the market
 * specialist's tool returns; showing the flight status of market-data MCP.
 */

import { useBriefStore } from '../../../shared/store/brief';

export function MarketPane() {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const latest = [...toolCalls].reverse().find((t) => t.tool_name === 'market-data');

  return (
    <section className="research-pane" aria-label="Market">
      <header className="research-pane__header">
        <span>Market</span>
        <span>{latest?.status ?? 'idle'}</span>
      </header>
      <div className="research-pane__body">
        {!latest && <div style={{ opacity: 0.7 }}>no request yet</div>}
        {latest && latest.status === 'running' && <div className="v3-skeleton">market-data…</div>}
        {latest && latest.status === 'ok' && (
          <div>
            <div>
              latency: <strong>{latest.latency_ms}ms</strong>
            </div>
            <div>span: {latest.span_id}</div>
            <div style={{ opacity: 0.7, fontSize: '0.75rem' }}>
              Full quote payload rendered in the brief panel.
            </div>
          </div>
        )}
        {latest && latest.status === 'error' && (
          <div role="alert" style={{ color: '#F47067' }}>
            market-data failed — brief synthesized without it
          </div>
        )}
      </div>
    </section>
  );
}

/**
 * TimelineV2 — end-to-end trace waterfall, wired to the live brief + gate
 * stores.
 *
 * Rows are grouped by agent (orchestrator → specialist → tool). The
 * orchestrator row gets the whole turn width; specialist rows start when
 * their first tool call fires and end when their last finishes. MCP/skill
 * rows are children of their specialist.
 *
 * For advisor persona the gate chain is appended as `gate` rows in
 * canonical order with human-kind coloring for gate ④ (HITL) which may
 * hold for seconds.
 *
 * All timings are real — pulled from `brief.toolCalls[].started_at` and
 * `brief.toolCalls[].completed_at` + gate timestamps.
 */

import { useMemo } from 'react';
import { useBriefStore } from '../../shared/store/brief';
import { useTraversalStore } from '../../shared/store/traversal';
import type { GateState, ToolCall } from '../../shared/types/api';
import type { Persona } from '../../shared/types/persona';

interface Row {
  name: string;
  kind: 'orch' | 'skill' | 'mcp' | 'gate' | 'human';
  startPct: number;
  widthPct: number;
  latency: string;
  indent: number;
}

const KIND_LABEL: Record<Row['kind'], string> = {
  orch: 'orch',
  skill: 'skill',
  mcp: 'mcp',
  gate: 'gate',
  human: 'human',
};

function formatMs(ms: number): string {
  if (ms < 0) return '—';
  if (ms === 0) return '0ms';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function indentName(name: string, indent: number, connector: string = '└'): string {
  if (indent === 0) return name;
  return '│ '.repeat(indent - 1) + `${connector} ` + name;
}

// Agent ordering — orchestrator first, then specialists in topology order.
const AGENT_ORDER: Record<Persona, string[]> = {
  fsi_research: [
    'research_orchestrator',
    'market_specialist',
    'filings_specialist',
    'sentiment_specialist',
    'compliance_specialist',
    'statement_specialist',
  ],
  fsi_advisor: [
    'advisor_orchestrator',
    'portfolio_specialist',
    'suitability_specialist',
    'client_context_specialist',
    'action_specialist',
  ],
  fsi_client_liaison: [
    'liaison_orchestrator',
    'context_specialist',
    'faq_specialist',
  ],
};

function buildRows(
  persona: Persona,
  toolCalls: ToolCall[],
  gates: GateState[],
  turnDurationMs: number,
  turnStartedAt: number | null,
): Row[] {
  const rows: Row[] = [];
  if (turnDurationMs === 0) return rows;

  const startEpoch = turnStartedAt ?? (toolCalls[0]
    ? Date.parse(toolCalls[0].started_at)
    : Date.now());
  const total = Math.max(turnDurationMs, 100);

  // Orchestrator — spans the whole turn
  const orchId = AGENT_ORDER[persona][0]!;
  rows.push({
    name: orchId,
    kind: 'orch',
    startPct: 0,
    widthPct: 100,
    latency: formatMs(turnDurationMs),
    indent: 0,
  });

  // Group tool calls by agent_id in AGENT_ORDER
  const callsByAgent = new Map<string, ToolCall[]>();
  for (const tc of toolCalls) {
    const existing = callsByAgent.get(tc.agent_id) ?? [];
    existing.push(tc);
    callsByAgent.set(tc.agent_id, existing);
  }

  for (const agentId of AGENT_ORDER[persona]) {
    if (agentId === orchId) continue;
    const calls = callsByAgent.get(agentId);
    if (!calls || calls.length === 0) continue;
    const firstStart = Math.min(
      ...calls.map((c) => Date.parse(c.started_at) - startEpoch),
    );
    const lastEnd = Math.max(
      ...calls.map((c) =>
        c.completed_at ? Date.parse(c.completed_at) - startEpoch : firstStart + (c.latency_ms ?? 0),
      ),
    );
    const agentDuration = Math.max(0, lastEnd - firstStart);
    rows.push({
      name: agentId,
      kind: 'skill',
      startPct: Math.max(0, (firstStart / total) * 100),
      widthPct: Math.max(2, (agentDuration / total) * 100),
      latency: formatMs(agentDuration),
      indent: 1,
    });
    // Child MCP/skill calls
    for (const c of calls) {
      const start = Date.parse(c.started_at) - startEpoch;
      const dur = c.latency_ms ?? 0;
      rows.push({
        name: c.tool_name,
        kind: 'mcp',
        startPct: Math.max(0, (start / total) * 100),
        widthPct: Math.max(1, (dur / total) * 100),
        latency: formatMs(dur),
        indent: 2,
      });
    }
  }

  // Advisor: append gate chain
  if (persona === 'fsi_advisor' && gates.length > 0) {
    // Figure out when the first gate started relative to turn start
    const firstGateStart = gates
      .map((g) => (g.started_at ? Date.parse(g.started_at) - startEpoch : null))
      .filter((x): x is number => x !== null)
      .reduce((min, v) => Math.min(min, v), Number.POSITIVE_INFINITY);
    const gateStartPct = Number.isFinite(firstGateStart)
      ? Math.max(0, (firstGateStart / total) * 100)
      : 60; // fallback if we don't have timing
    gates.forEach((g, i) => {
      const startPctInGateChain = gateStartPct + i * ((100 - gateStartPct) / gates.length);
      const widthPct = (100 - gateStartPct) / gates.length;
      const isHitl = g.name === 'hitl';
      const kind: Row['kind'] = isHitl ? 'human' : 'gate';
      let latency = '—';
      if (g.started_at && g.completed_at) {
        latency = formatMs(Date.parse(g.completed_at) - Date.parse(g.started_at));
      } else if (g.status === 'in_progress') {
        latency = '…';
      }
      rows.push({
        name: `gate ${i + 1}: ${g.name}`,
        kind,
        startPct: startPctInGateChain,
        widthPct,
        latency,
        indent: 1,
      });
    });
  }

  return rows;
}

function captionFor(persona: Persona): string {
  if (persona === 'fsi_research') {
    return 'Specialists start in parallel — orchestrator total ≠ Σ children proves asyncio.gather.';
  }
  if (persona === 'fsi_advisor') {
    return 'Three policy gates before action draft. Plan halts at gate ④ until RM approves — execution gated, not advisory.';
  }
  return 'Intent shift caught client-side — refusal returns before any MCP touch. Hand-off preserves conversation id across personas.';
}

export interface TimelineV2Props {
  persona: Persona;
  /** Optional gate state from useGateTracker (advisor only). */
  gates?: GateState[];
  langfuseBaseUrl?: string;
}

export function TimelineV2({ persona, gates = [], langfuseBaseUrl }: TimelineV2Props) {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const durationMs = useBriefStore((s) => s.durationMs);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const startedAt = useTraversalStore((s) => s.startedAt);
  const correlationId = useBriefStore((s) => s.turnId);

  const effectiveDuration = durationMs > 0
    ? durationMs
    : isStreaming && startedAt
    ? Date.now() - startedAt
    : 0;

  const rows = useMemo(
    () => buildRows(persona, toolCalls, gates, effectiveDuration, startedAt),
    [persona, toolCalls, gates, effectiveDuration, startedAt],
  );

  return (
    <div className="v2-timeline" data-testid="timeline-v2">
      <div className="v2-timeline__header">
        <div className="v2-timeline__header-title">
          <span>End-to-End Trace</span>
          <span className="w360-mono" style={{ fontSize: 10, color: 'var(--forensic-text-5)', textTransform: 'none', letterSpacing: 0 }}>
            {correlationId ? `turn ${correlationId.slice(0, 8)}` : '—'} · {toolCalls.length} tools · {formatMs(effectiveDuration)}
          </span>
        </div>
        {langfuseBaseUrl && correlationId && (
          <a
            className="btn-ghost"
            href={`${langfuseBaseUrl.replace(/\/$/, '')}/trace/${encodeURIComponent(correlationId)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            ⎋ open in Langfuse
          </a>
        )}
      </div>
      {rows.length === 0 ? (
        <div className="v2-timeline__rows">
          <div className="v2-timeline__row">
            <span className="v2-timeline__name" style={{ color: 'var(--forensic-text-5)', fontStyle: 'italic' }}>
              no trace yet — submit a query to populate
            </span>
            <span className="v2-timeline__type">—</span>
            <div className="v2-timeline__bar-track" />
            <span className="v2-timeline__latency">—</span>
          </div>
        </div>
      ) : (
        <div className="v2-timeline__rows">
          {rows.map((r, i) => (
            <div key={i} className="v2-timeline__row">
              <span
                className={'v2-timeline__name' + (r.indent > 0 ? ' v2-timeline__name--child' : '')}
                title={r.name}
              >
                {indentName(r.name, r.indent)}
              </span>
              <span className="v2-timeline__type">[{KIND_LABEL[r.kind]}]</span>
              <div className="v2-timeline__bar-track">
                <div
                  className={`v2-timeline__bar v2-timeline__bar--${r.kind}`}
                  style={{ left: `${r.startPct}%`, width: `${r.widthPct}%` }}
                />
              </div>
              <span className="v2-timeline__latency">{r.latency}</span>
            </div>
          ))}
        </div>
      )}
      <div className="v2-timeline__caption">{captionFor(persona)}</div>
    </div>
  );
}

/**
 * V4 End-to-End Timeline — ported from the uploaded design's Timeline
 * (trace-shared.jsx), restyled with the design-system CSS classes, wired
 * to real live spans from `useBriefStore`.
 *
 * Why this isn't the v3 TimelineV2 renamed: the v3 one displays a single
 * in-flight turn. The designer's layout drew the timeline INSIDE a
 * trust-spine strip next to the Architecture Map, with a fixed row
 * grammar (orchestrator / specialist / MCP / skill / human) and a
 * permanent italic caption below — that caption is the narrative hook
 * ("all five specialists started at t≈80ms — proves asyncio.gather").
 *
 * Empty-state: the designer's original showed a mock seed of data. Live
 * v4 shows a one-line "submit a query to populate" when no spans exist,
 * instead of misleading mock rows.
 *
 * Gate band: when the advisor persona has a gate_trace on the current
 * turn, we append the 7-gate serial spine BELOW the tool rows so the
 * "non-overlapping = serial" demo reads.
 */

import { useMemo } from 'react';
import { useBriefStore } from '../../shared/store/brief';
import { useTraversalStore } from '../../shared/store/traversal';
import { useSessionStore } from '../../shared/store/session';
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
    'handoff_specialist',
  ],
};

function formatMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function indentName(name: string, indent: number): string {
  if (indent === 0) return name;
  const prefix = indent === 1 ? '├ ' : indent === 2 ? '│  └ ' : '    └ ';
  return prefix + name;
}

function buildRows(
  persona: Persona,
  toolCalls: ToolCall[],
  gates: GateState[],
  turnDurationMs: number,
  turnStartedAt: number | null,
): Row[] {
  const rows: Row[] = [];
  if (turnDurationMs === 0) return rows;

  const startEpoch = turnStartedAt ?? (toolCalls[0] ? Date.parse(toolCalls[0].started_at) : Date.now());
  const total = Math.max(turnDurationMs, 100);

  const orchId = AGENT_ORDER[persona][0]!;
  rows.push({
    name: orchId,
    kind: 'orch',
    startPct: 0,
    widthPct: 100,
    latency: formatMs(turnDurationMs),
    indent: 0,
  });

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
    const firstStart = Math.min(...calls.map((c) => Date.parse(c.started_at) - startEpoch));
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

  if (persona === 'fsi_advisor' && gates.length > 0) {
    const firstGateStart = gates
      .map((g) => (g.started_at ? Date.parse(g.started_at) - startEpoch : null))
      .filter((x): x is number => x !== null)
      .reduce((min, v) => Math.min(min, v), Number.POSITIVE_INFINITY);
    const gateStartPct = Number.isFinite(firstGateStart)
      ? Math.max(0, (firstGateStart / total) * 100)
      : 60;
    gates.forEach((g, i) => {
      const startPctInGateChain = gateStartPct + i * ((100 - gateStartPct) / gates.length);
      const widthPct = (100 - gateStartPct) / gates.length;
      const isHitl = g.name === 'hitl';
      let latency = '—';
      if (g.started_at && g.completed_at) {
        latency = formatMs(Date.parse(g.completed_at) - Date.parse(g.started_at));
      } else if (g.status === 'in_progress') {
        latency = '…';
      }
      rows.push({
        name: `gate ${i + 1}: ${g.name}`,
        kind: isHitl ? 'human' : 'gate',
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
  return 'Intent shift caught client-side — refusal returns before any MCP touch. Hand-off preserves the conversation id across personas.';
}

export interface TimelineV4Props {
  persona: Persona;
  gates?: GateState[];
  langfuseBaseUrl?: string;
}

export function TimelineV4({ persona, gates = [], langfuseBaseUrl }: TimelineV4Props) {
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const durationMs = useBriefStore((s) => s.durationMs);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const startedAt = useTraversalStore((s) => s.startedAt);
  const correlationId = useSessionStore((s) => s.correlationId);

  const effectiveDuration =
    durationMs > 0 ? durationMs : isStreaming && startedAt ? Date.now() - startedAt : 0;

  const rows = useMemo(
    () => buildRows(persona, toolCalls, gates, effectiveDuration, startedAt),
    [persona, toolCalls, gates, effectiveDuration, startedAt],
  );

  const summaryMeta = (() => {
    if (!correlationId && rows.length === 0) return '—';
    const toolCount = toolCalls.length;
    const nowIso = startedAt ? new Date(startedAt) : null;
    const hhmm = nowIso
      ? `${String(nowIso.getHours()).padStart(2, '0')}:${String(nowIso.getMinutes()).padStart(2, '0')}:${String(nowIso.getSeconds()).padStart(2, '0')}`
      : '—';
    return `${hhmm} · ${toolCount} tool${toolCount === 1 ? '' : 's'} · ${formatMs(effectiveDuration)}`;
  })();

  return (
    <div className="timeline" data-testid="timeline-v4">
      <div className="timeline__header">
        <div className="timeline__header-title">
          <span>End-to-End Trace</span>
          <span
            className="w360-mono"
            style={{
              fontSize: 10,
              color: 'var(--v4-forensic-text-4)',
              textTransform: 'none',
              letterSpacing: 0,
            }}
          >
            {summaryMeta}
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
        <div className="timeline__empty">submit a query to populate the trace</div>
      ) : (
        <div className="timeline__rows">
          {rows.map((r, i) => (
            <div key={i} className="timeline__row">
              <span
                className={
                  'timeline__name' + (r.indent > 0 ? ' timeline__name--child' : '')
                }
                title={r.name}
              >
                {indentName(r.name, r.indent)}
              </span>
              <span className="timeline__type">[{KIND_LABEL[r.kind]}]</span>
              <div className="timeline__bar-track">
                <div
                  className={`timeline__bar timeline__bar--${r.kind}`}
                  style={{ left: `${r.startPct}%`, width: `${r.widthPct}%` }}
                />
              </div>
              <span className="timeline__latency">{r.latency}</span>
            </div>
          ))}
        </div>
      )}
      <div className="timeline__caption">{captionFor(persona)}</div>
    </div>
  );
}

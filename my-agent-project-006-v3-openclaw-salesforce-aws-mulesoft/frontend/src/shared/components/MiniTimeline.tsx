/**
 * Waterfall bars for a single turn — lives inside an expanded EndToEndTrace
 * row. Proves parallelism: bars that start at the same time stack vertically
 * at the same x-coordinate instead of sequencing left-to-right.
 *
 * Uses @visx/scale for the x mapping and @visx/shape for bar rendering.
 * No new deps.
 *
 * Rendering rules:
 *  - x offset = started_at - turnStartedAt (ms)
 *  - width   = latency_ms (or now-started if still running)
 *  - y       = one row per agent_id, in order of first appearance
 *  - color   = ok=#04844b, error=#c23934, running=#1B96FF
 *
 * Falls back to a "no timing data" placeholder when all bars would be zero
 * width or timestamps are malformed.
 */

import { useMemo } from 'react';
import { scaleLinear } from '@visx/scale';
import { Bar } from '@visx/shape';
import type { ToolCall } from '../types/api';

export interface MiniTimelineProps {
  toolCalls: ToolCall[];
  turnStartedAt: number;
  turnEndedAt: number;
  height?: number;
  /** Optional: gate events from the turn's gateTrace. When present, each gate
   *  renders as its own row in a separate "gates" band below the tool calls —
   *  proves "7 non-overlapping bars = serial spine" visually. */
  gateTrace?: Array<{ gate: string; status: string; ts: number }>;
}

const STATUS_COLOR: Record<ToolCall['status'], string> = {
  ok: '#04844b',
  error: '#c23934',
  running: '#1B96FF',
};

const ROW_HEIGHT = 18;
const ROW_GAP = 4;
const LEFT_GUTTER = 140; // room for agent labels
const RIGHT_PAD = 16;
const AXIS_HEIGHT = 18;

interface ComputedBar {
  key: string;
  row: number;
  agent: string;
  tool: string;
  startMs: number;
  durMs: number;
  status: ToolCall['status'];
  latencyLabel: string;
}

function parseTs(ts: string | undefined): number | null {
  if (!ts) return null;
  const n = Date.parse(ts);
  return Number.isFinite(n) ? n : null;
}

export function MiniTimeline({
  toolCalls,
  turnStartedAt,
  turnEndedAt,
  height = 140,
  gateTrace,
}: MiniTimelineProps) {
  const { bars, rows, totalMs, malformed, gateBars } = useMemo(() => {
    const rowMap = new Map<string, number>();
    const computed: ComputedBar[] = [];
    let maxEnd = 0;
    let anyMalformed = false;

    for (const tc of toolCalls) {
      const startedAbs = parseTs(tc.started_at);
      if (startedAbs === null) {
        anyMalformed = true;
        continue;
      }
      const startMs = Math.max(0, startedAbs - turnStartedAt);
      // prefer explicit latency_ms, else derive from completed_at,
      // else assume running → extend to now (or turnEndedAt).
      let durMs: number;
      if (typeof tc.latency_ms === 'number' && tc.latency_ms >= 0) {
        durMs = tc.latency_ms;
      } else {
        const endedAbs = parseTs(tc.completed_at);
        if (endedAbs !== null) {
          durMs = Math.max(0, endedAbs - startedAbs);
        } else {
          durMs = Math.max(0, turnEndedAt - startedAbs);
        }
      }
      const row = rowMap.has(tc.agent_id)
        ? (rowMap.get(tc.agent_id) as number)
        : (() => {
            const next = rowMap.size;
            rowMap.set(tc.agent_id, next);
            return next;
          })();
      computed.push({
        key: tc.span_id,
        row,
        agent: tc.agent_id,
        tool: tc.tool_name,
        startMs,
        durMs,
        status: tc.status,
        latencyLabel: `${Math.round(durMs)}ms`,
      });
      if (startMs + durMs > maxEnd) maxEnd = startMs + durMs;
    }

    // Gate bars: one bar per gate from in_progress → passed/failed. Proves
    // serial-by-design visually — 7 non-overlapping bars in a single row.
    const gateStarts = new Map<string, number>();
    const gBars: ComputedBar[] = [];
    const trace = gateTrace ?? [];
    trace.forEach((g, i) => {
      const ts = g.ts;
      if (g.status === 'in_progress' || g.status === 'pending') {
        gateStarts.set(g.gate, ts);
      } else if (g.status === 'passed' || g.status === 'failed' || g.status === 'skipped') {
        const startAbs = gateStarts.get(g.gate) ?? ts;
        const startMs = Math.max(0, startAbs - turnStartedAt);
        const durMs = Math.max(0, ts - startAbs);
        gateStarts.delete(g.gate);
        gBars.push({
          key: `gate-${g.gate}-${i}`,
          row: 0, // all gates share row 0 in the gate band
          agent: g.gate,
          tool: g.gate,
          startMs,
          durMs,
          status: g.status === 'failed' ? 'error' : 'ok',
          latencyLabel: `${Math.round(durMs)}ms`,
        });
        if (startMs + durMs > maxEnd) maxEnd = startMs + durMs;
      }
    });
    // Drop any unresolved in_progress gates with no close — show zero-width.
    gateStarts.forEach((startAbs, gate) => {
      const startMs = Math.max(0, startAbs - turnStartedAt);
      gBars.push({
        key: `gate-${gate}-open`,
        row: 0,
        agent: gate,
        tool: gate,
        startMs,
        durMs: Math.max(0, turnEndedAt - startAbs),
        status: 'running',
        latencyLabel: 'open',
      });
    });

    const turnSpan = Math.max(0, turnEndedAt - turnStartedAt);
    const total = Math.max(maxEnd, turnSpan, 1);
    const rows = Array.from(rowMap.entries()).map(([agent, row]) => ({ agent, row }));
    return { bars: computed, rows, totalMs: total, malformed: anyMalformed, gateBars: gBars };
  }, [toolCalls, turnStartedAt, turnEndedAt, gateTrace]);

  // Fallback: nothing worth drawing. Still keep structure so tests can find it.
  const allZero = bars.length > 0 && bars.every((b) => b.durMs === 0);
  const hasGateBars = gateBars.length > 0;
  if ((bars.length === 0 || allZero || malformed) && !hasGateBars) {
    if (typeof process !== 'undefined' && process.env?.NODE_ENV !== 'production' && (allZero || malformed)) {
      // eslint-disable-next-line no-console
      console.warn(
        '[MiniTimeline] no timing data to render',
        { bars: bars.length, allZero, malformed, gateBars: gateBars.length },
      );
    }
    return (
      <div
        className="v3-mini-timeline v3-mini-timeline--empty"
        role="note"
        data-testid="mini-timeline-empty"
        style={{ height }}
      >
        <span>no timing data</span>
      </div>
    );
  }

  const innerWidth = 560; // SVG viewBox units; container is responsive via CSS
  const plotWidth = innerWidth - LEFT_GUTTER - RIGHT_PAD;
  const xScale = scaleLinear<number>({
    domain: [0, totalMs],
    range: [0, plotWidth],
    clamp: true,
  });

  const GATE_BAND_HEIGHT = hasGateBars ? ROW_HEIGHT + ROW_GAP + 10 : 0;
  const toolBandHeight = rows.length * (ROW_HEIGHT + ROW_GAP) + ROW_GAP;
  const svgHeight = Math.max(
    height,
    AXIS_HEIGHT + toolBandHeight + GATE_BAND_HEIGHT + ROW_GAP,
  );

  // ms-grid ticks: pick a ~5-tick grid rounded to 100/500/1000/2000 steps.
  const ticks = buildTicks(totalMs);

  return (
    <div
      className="v3-mini-timeline"
      role="figure"
      aria-label="Tool-call waterfall timeline"
      style={{ maxHeight: height, overflowY: 'auto' }}
    >
      <svg
        viewBox={`0 0 ${innerWidth} ${svgHeight}`}
        width="100%"
        height={svgHeight}
        preserveAspectRatio="xMinYMin meet"
        data-testid="mini-timeline-svg"
      >
        {/* axis */}
        <g transform={`translate(${LEFT_GUTTER}, 0)`}>
          {ticks.map((t) => (
            <g key={t} transform={`translate(${xScale(t)}, 0)`}>
              <line
                y1={AXIS_HEIGHT - 4}
                y2={svgHeight}
                stroke="#1C2B3F"
                strokeDasharray="2 3"
                strokeWidth={1}
              />
              <text
                x={2}
                y={AXIS_HEIGHT - 6}
                fontSize={9}
                fill="#8B949E"
                fontFamily="SF Mono, Menlo, monospace"
              >
                {formatTick(t)}
              </text>
            </g>
          ))}
        </g>

        {/* row labels */}
        <g>
          {rows.map(({ agent, row }) => (
            <text
              key={agent}
              x={LEFT_GUTTER - 8}
              y={AXIS_HEIGHT + row * (ROW_HEIGHT + ROW_GAP) + ROW_HEIGHT * 0.7}
              fontSize={10}
              textAnchor="end"
              fill="#C9D1D9"
              fontFamily="SF Mono, Menlo, monospace"
            >
              {truncate(agent, 20)}
            </text>
          ))}
        </g>

        {/* bars */}
        <g transform={`translate(${LEFT_GUTTER}, ${AXIS_HEIGHT})`}>
          {bars.map((b) => {
            const x = xScale(b.startMs);
            const w = Math.max(2, xScale(b.startMs + b.durMs) - xScale(b.startMs));
            const y = b.row * (ROW_HEIGHT + ROW_GAP);
            return (
              <g
                key={b.key}
                data-testid={`mini-timeline-bar-${b.key}`}
                data-start={b.startMs}
                data-duration={b.durMs}
                data-status={b.status}
              >
                <title>
                  {b.tool} · {b.agent} · {b.latencyLabel}
                </title>
                <Bar
                  className="v3-mini-timeline__bar"
                  x={x}
                  y={y}
                  width={w}
                  height={ROW_HEIGHT}
                  fill={STATUS_COLOR[b.status]}
                  rx={3}
                  ry={3}
                />
                {w > 40 && (
                  <text
                    x={x + 4}
                    y={y + ROW_HEIGHT * 0.7}
                    fontSize={9}
                    fill="#0B1B2F"
                    fontFamily="SF Mono, Menlo, monospace"
                    pointerEvents="none"
                  >
                    {b.latencyLabel}
                  </text>
                )}
              </g>
            );
          })}
        </g>

        {/* Gate band — renders the 7-gate serial spine below the tool calls.
            All gate bars share one row so "non-overlapping = serial" reads
            visually. Amber fill matches the on-map gate styling. */}
        {hasGateBars && (
          <g
            transform={`translate(${LEFT_GUTTER}, ${AXIS_HEIGHT + toolBandHeight + ROW_GAP})`}
            data-testid="mini-timeline-gate-band"
          >
            <line
              x1={-LEFT_GUTTER + 8}
              x2={plotWidth}
              y1={-2}
              y2={-2}
              stroke="#2B3A52"
              strokeWidth={1}
            />
            <text
              x={-8}
              y={ROW_HEIGHT * 0.7}
              fontSize={10}
              textAnchor="end"
              fill="#E0BE8E"
              fontFamily="SF Mono, Menlo, monospace"
            >
              7-gate spine
            </text>
            {gateBars.map((g) => {
              const x = xScale(g.startMs);
              const w = Math.max(2, xScale(g.startMs + g.durMs) - xScale(g.startMs));
              return (
                <g
                  key={g.key}
                  data-testid={`mini-timeline-gate-${g.agent}`}
                  data-start={g.startMs}
                  data-duration={g.durMs}
                  data-status={g.status}
                >
                  <title>
                    {g.agent} · {g.latencyLabel}
                  </title>
                  <Bar
                    className="v3-mini-timeline__bar v3-mini-timeline__gate-bar"
                    x={x}
                    y={0}
                    width={w}
                    height={ROW_HEIGHT}
                    fill={g.status === 'error' ? '#c23934' : g.status === 'running' ? '#1B96FF' : '#B07A3D'}
                    rx={2}
                    ry={2}
                  />
                </g>
              );
            })}
          </g>
        )}
      </svg>
    </div>
  );
}

function buildTicks(totalMs: number): number[] {
  const target = 5;
  const raw = totalMs / target;
  const candidates = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000];
  let step: number = candidates[candidates.length - 1] ?? 1000;
  for (const c of candidates) {
    if (c >= raw) {
      step = c;
      break;
    }
  }
  const ticks: number[] = [];
  for (let t = 0; t <= totalMs; t += step) ticks.push(t);
  if (ticks[ticks.length - 1] !== totalMs) ticks.push(totalMs);
  return ticks;
}

function formatTick(ms: number): string {
  if (ms === 0) return '0';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)}s`;
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + '…';
}

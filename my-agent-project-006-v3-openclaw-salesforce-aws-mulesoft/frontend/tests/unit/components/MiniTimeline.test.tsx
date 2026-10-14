import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MiniTimeline } from '../../../src/shared/components/MiniTimeline';
import type { ToolCall } from '../../../src/shared/types/api';

const T0 = Date.UTC(2026, 0, 1, 12, 0, 0);
const iso = (offsetMs: number) => new Date(T0 + offsetMs).toISOString();

const call = (o: Partial<ToolCall>): ToolCall => ({
  span_id: 's',
  tool_name: 't',
  agent_id: 'a',
  started_at: iso(0),
  completed_at: iso(100),
  status: 'ok',
  latency_ms: 100,
  ...o,
});

describe('MiniTimeline', () => {
  it('places parallel bars at the same x-offset when they share started_at', () => {
    const calls: ToolCall[] = [
      call({ span_id: 'a1', agent_id: 'market', started_at: iso(100), latency_ms: 500 }),
      call({ span_id: 'a2', agent_id: 'filings', started_at: iso(100), latency_ms: 800 }),
      call({ span_id: 'a3', agent_id: 'sentiment', started_at: iso(100), latency_ms: 300 }),
    ];
    render(
      <MiniTimeline toolCalls={calls} turnStartedAt={T0} turnEndedAt={T0 + 1000} />,
    );
    const a1 = screen.getByTestId('mini-timeline-bar-a1');
    const a2 = screen.getByTestId('mini-timeline-bar-a2');
    const a3 = screen.getByTestId('mini-timeline-bar-a3');
    // all share the same relative start (100ms after turn start)
    expect(a1.getAttribute('data-start')).toBe('100');
    expect(a2.getAttribute('data-start')).toBe('100');
    expect(a3.getAttribute('data-start')).toBe('100');
  });

  it('scales bar widths to latency', () => {
    const calls: ToolCall[] = [
      call({ span_id: 'short', started_at: iso(0), latency_ms: 100 }),
      call({ span_id: 'long', started_at: iso(0), latency_ms: 900, agent_id: 'other' }),
    ];
    const { container } = render(
      <MiniTimeline toolCalls={calls} turnStartedAt={T0} turnEndedAt={T0 + 1000} />,
    );
    const shortBar = container.querySelector(
      '[data-testid="mini-timeline-bar-short"] rect',
    ) as SVGRectElement | null;
    const longBar = container.querySelector(
      '[data-testid="mini-timeline-bar-long"] rect',
    ) as SVGRectElement | null;
    expect(shortBar).not.toBeNull();
    expect(longBar).not.toBeNull();
    const shortW = parseFloat(shortBar!.getAttribute('width') as string);
    const longW = parseFloat(longBar!.getAttribute('width') as string);
    expect(longW).toBeGreaterThan(shortW);
  });

  it('uses distinct colors per status', () => {
    const calls: ToolCall[] = [
      call({ span_id: 'ok', status: 'ok', started_at: iso(0), latency_ms: 100 }),
      call({ span_id: 'err', status: 'error', started_at: iso(100), latency_ms: 100, agent_id: 'b' }),
      call({ span_id: 'run', status: 'running', started_at: iso(200), latency_ms: 100, agent_id: 'c' }),
    ];
    const { container } = render(
      <MiniTimeline toolCalls={calls} turnStartedAt={T0} turnEndedAt={T0 + 500} />,
    );
    const ok = container.querySelector('[data-testid="mini-timeline-bar-ok"] rect')?.getAttribute('fill');
    const err = container.querySelector('[data-testid="mini-timeline-bar-err"] rect')?.getAttribute('fill');
    const run = container.querySelector('[data-testid="mini-timeline-bar-run"] rect')?.getAttribute('fill');
    expect(ok).toBeTruthy();
    expect(err).toBeTruthy();
    expect(run).toBeTruthy();
    expect(ok).not.toEqual(err);
    expect(ok).not.toEqual(run);
    expect(err).not.toEqual(run);
  });

  it('shows "no timing data" when toolCalls is empty', () => {
    render(<MiniTimeline toolCalls={[]} turnStartedAt={T0} turnEndedAt={T0 + 100} />);
    expect(screen.getByTestId('mini-timeline-empty')).toHaveTextContent(/no timing data/i);
  });

  it('does not crash and shows placeholder for malformed timestamps', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const calls: ToolCall[] = [
      call({ span_id: 'bad', started_at: 'not-a-date', latency_ms: 100 }),
    ];
    render(
      <MiniTimeline toolCalls={calls} turnStartedAt={T0} turnEndedAt={T0 + 500} />,
    );
    expect(screen.getByTestId('mini-timeline-empty')).toBeInTheDocument();
    warn.mockRestore();
  });
});


describe('MiniTimeline — gate band', () => {
  it('renders a gate band when gateTrace has matched in_progress+passed events', () => {
    render(
      <MiniTimeline
        toolCalls={[]}
        turnStartedAt={T0}
        turnEndedAt={T0 + 1000}
        gateTrace={[
          { gate: 'guardrails', status: 'in_progress', ts: T0 + 10 },
          { gate: 'guardrails', status: 'passed', ts: T0 + 60 },
          { gate: 'compliance', status: 'in_progress', ts: T0 + 70 },
          { gate: 'compliance', status: 'passed', ts: T0 + 220 },
        ]}
      />,
    );
    expect(screen.getByTestId('mini-timeline-gate-band')).toBeInTheDocument();
    expect(screen.getByTestId('mini-timeline-gate-guardrails')).toBeInTheDocument();
    expect(screen.getByTestId('mini-timeline-gate-compliance')).toBeInTheDocument();
  });

  it('gate bars are non-overlapping on the time axis (serial proof)', () => {
    const { container } = render(
      <MiniTimeline
        toolCalls={[]}
        turnStartedAt={T0}
        turnEndedAt={T0 + 1000}
        gateTrace={[
          { gate: 'guardrails', status: 'in_progress', ts: T0 + 10 },
          { gate: 'guardrails', status: 'passed', ts: T0 + 60 },
          { gate: 'compliance', status: 'in_progress', ts: T0 + 70 },
          { gate: 'compliance', status: 'passed', ts: T0 + 220 },
        ]}
      />,
    );
    const g1 = container.querySelector(
      '[data-testid="mini-timeline-gate-guardrails"]',
    ) as SVGGElement | null;
    const g2 = container.querySelector(
      '[data-testid="mini-timeline-gate-compliance"]',
    ) as SVGGElement | null;
    expect(g1).not.toBeNull();
    expect(g2).not.toBeNull();
    const g1Start = Number(g1!.getAttribute('data-start'));
    const g1Dur = Number(g1!.getAttribute('data-duration'));
    const g2Start = Number(g2!.getAttribute('data-start'));
    // gate2 must start AFTER gate1 ends — serial by design
    expect(g2Start).toBeGreaterThanOrEqual(g1Start + g1Dur);
  });

  it('renders failed gate with error color (gate 3 DENY scenario)', () => {
    const { container } = render(
      <MiniTimeline
        toolCalls={[]}
        turnStartedAt={T0}
        turnEndedAt={T0 + 500}
        gateTrace={[
          { gate: 'compliance', status: 'in_progress', ts: T0 + 10 },
          { gate: 'compliance', status: 'failed', ts: T0 + 200 },
          { gate: 'audit', status: 'in_progress', ts: T0 + 210 },
          { gate: 'audit', status: 'passed', ts: T0 + 260 },
        ]}
      />,
    );
    const complianceBar = container.querySelector(
      '[data-testid="mini-timeline-gate-compliance"]',
    );
    const auditBar = container.querySelector(
      '[data-testid="mini-timeline-gate-audit"]',
    );
    expect(complianceBar?.getAttribute('data-status')).toBe('error');
    // Audit still fires even on compliance DENY — this is the narrative proof.
    expect(auditBar?.getAttribute('data-status')).toBe('ok');
  });
});

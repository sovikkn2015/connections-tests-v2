/**
 * GatesTrackerV2 — renders all 7 gates, reflects status transitions, shows
 * latency derived from started_at/completed_at timestamps.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GatesTrackerV2 } from '../../../src/v2/atoms/GatesTrackerV2';
import { SEVEN_GATES, type GateState } from '../../../src/shared/types/api';

describe('GatesTrackerV2', () => {
  it('renders all seven gates with canonical numerals', () => {
    const gates: GateState[] = SEVEN_GATES.map((name) => ({ name, status: 'pending' }));
    render(<GatesTrackerV2 gates={gates} />);
    for (const name of SEVEN_GATES) {
      const cell = screen.getByTestId(`v2-gate-${name}`);
      expect(cell).toBeInTheDocument();
      expect(cell).toHaveAttribute('data-status', 'pending');
    }
    // Canonical numerals ①..⑦ present
    expect(screen.getByText(/gate 1 \/ 7/)).toBeInTheDocument();
    expect(screen.getByText(/gate 7 \/ 7/)).toBeInTheDocument();
  });

  it('shows dash for pending gates', () => {
    const gates: GateState[] = SEVEN_GATES.map((name) => ({ name, status: 'pending' }));
    render(<GatesTrackerV2 gates={gates} />);
    // All detail texts should end in "— " (dash) for pending.
    const dashCount = screen.getAllByText(/·\s*—\s*$/);
    expect(dashCount.length).toBe(7);
  });

  it('derives latency from started_at/completed_at for passed gates', () => {
    const started = new Date('2026-04-30T06:14:30.000Z').toISOString();
    const completed = new Date('2026-04-30T06:14:30.220Z').toISOString(); // 220ms
    const gates: GateState[] = SEVEN_GATES.map((name) => ({
      name,
      status: name === 'guardrails' ? 'passed' : 'pending',
      started_at: name === 'guardrails' ? started : undefined,
      completed_at: name === 'guardrails' ? completed : undefined,
    }));
    render(<GatesTrackerV2 gates={gates} />);
    const guardrails = screen.getByTestId('v2-gate-guardrails');
    expect(guardrails).toHaveAttribute('data-status', 'passed');
    expect(guardrails.textContent).toMatch(/220ms/);
  });

  it('shows "…" for in_progress gate', () => {
    const gates: GateState[] = SEVEN_GATES.map((name) => ({
      name,
      status: name === 'hitl' ? 'in_progress' : 'pending',
    }));
    render(<GatesTrackerV2 gates={gates} />);
    const hitl = screen.getByTestId('v2-gate-hitl');
    expect(hitl).toHaveAttribute('data-status', 'in_progress');
    expect(hitl.textContent).toMatch(/…/);
  });
});

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SevenGateTracker } from '../../../src/v1/components/SevenGateTracker';
import { SEVEN_GATES, type GateState } from '../../../src/shared/types/api';

describe('SevenGateTracker', () => {
  it('renders all seven gates in canonical order', () => {
    const gates: GateState[] = SEVEN_GATES.map((name) => ({ name, status: 'pending' }));
    render(<SevenGateTracker gates={gates} />);
    for (const gate of SEVEN_GATES) {
      const cell = screen.getByTestId(`gate-${gate}`);
      expect(cell).toBeInTheDocument();
      expect(cell).toHaveAttribute('data-status', 'pending');
    }
  });

  it('reflects gate status transitions', () => {
    const gates: GateState[] = SEVEN_GATES.map((name) => ({
      name,
      status: name === 'hitl' ? 'in_progress' : name === 'guardrails' ? 'passed' : 'pending',
    }));
    render(<SevenGateTracker gates={gates} />);
    expect(screen.getByTestId('gate-guardrails')).toHaveAttribute('data-status', 'passed');
    expect(screen.getByTestId('gate-hitl')).toHaveAttribute('data-status', 'in_progress');
  });
});

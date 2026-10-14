import { describe, it, expect } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useGateTracker } from '../../../src/shared/hooks/useGateTracker';
import { SEVEN_GATES } from '../../../src/shared/types/api';

describe('useGateTracker', () => {
  it('starts with 7 pending gates in canonical order', () => {
    const { result } = renderHook(() => useGateTracker());
    expect(result.current.gates.map((g) => g.name)).toEqual([...SEVEN_GATES]);
    expect(result.current.gates.every((g) => g.status === 'pending')).toBe(true);
  });

  it('updates one gate at a time on gate events', () => {
    const { result } = renderHook(() => useGateTracker());
    act(() => {
      result.current.handleGateEvent({
        type: 'gate_passed',
        turn_id: 't1',
        plan_id: 'plan-a',
        gate: 'guardrails',
        status: 'passed',
      });
    });
    expect(result.current.activePlanId).toBe('plan-a');
    expect(result.current.gates.find((g) => g.name === 'guardrails')!.status).toBe('passed');
    expect(result.current.gates.find((g) => g.name === 'mnpi_filter')!.status).toBe('pending');
  });

  it('reset() clears all gates', () => {
    const { result } = renderHook(() => useGateTracker());
    act(() => {
      result.current.handleGateEvent({
        type: 'gate_passed',
        turn_id: 't',
        plan_id: 'p',
        gate: 'guardrails',
        status: 'passed',
      });
      result.current.reset();
    });
    expect(result.current.gates.every((g) => g.status === 'pending')).toBe(true);
    expect(result.current.activePlanId).toBeNull();
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useIntentPrefetch, extractTickers } from '../../../src/shared/hooks/useIntentPrefetch';

describe('extractTickers', () => {
  it('finds uppercase tickers on word boundaries', () => {
    expect(extractTickers('Research NVDA and AMD earnings')).toEqual(['NVDA', 'AMD']);
  });
  it('deduplicates', () => {
    expect(extractTickers('NVDA NVDA NVDA')).toEqual(['NVDA']);
  });
  it('ignores lowercase', () => {
    expect(extractTickers('nvda is a stock')).toEqual([]);
  });
});

describe('useIntentPrefetch', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('debounces and fires prefetch for detected tickers', () => {
    const onPrefetch = vi.fn();
    const { rerender } = renderHook(
      ({ text }: { text: string }) => useIntentPrefetch(text, { onPrefetch, debounceMs: 200 }),
      { initialProps: { text: '' } },
    );
    rerender({ text: 'Research NVDA ahead' });
    vi.advanceTimersByTime(100);
    expect(onPrefetch).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(onPrefetch).toHaveBeenCalledWith({ type: 'prefetch', tickers: ['NVDA'] });
  });

  it('does not re-fire for the same ticker set', () => {
    const onPrefetch = vi.fn();
    const { rerender } = renderHook(
      ({ text }: { text: string }) => useIntentPrefetch(text, { onPrefetch, debounceMs: 100 }),
      { initialProps: { text: 'NVDA' } },
    );
    vi.advanceTimersByTime(150);
    expect(onPrefetch).toHaveBeenCalledTimes(1);

    rerender({ text: 'NVDA earnings' });
    vi.advanceTimersByTime(150);
    expect(onPrefetch).toHaveBeenCalledTimes(1);
  });
});

/**
 * Intent-driven prefetch.
 *
 * As the user types, we watch for ticker-like tokens (1-5 uppercase letters on
 * a word boundary). On detection, after a 400ms debounce, we fire a session
 * warm request so market-data, sec-edgar, and news-search MCPs are already
 * warm by the time Enter is hit (narrative §6 "Intent-driven prefetch").
 *
 * The server handles fan-out; the frontend just emits the hint.
 */

import { useEffect, useRef } from 'react';
import type { OutboundMessage } from '../types/agent';

const TICKER_PATTERN = /\b[A-Z]{1,5}\b/g;
const DEBOUNCE_MS = 400;

export function extractTickers(text: string): string[] {
  const matches = text.match(TICKER_PATTERN) ?? [];
  return Array.from(new Set(matches)).filter((t) => t.length >= 1 && t.length <= 5);
}

export interface UseIntentPrefetchOptions {
  onPrefetch: (msg: Extract<OutboundMessage, { type: 'prefetch' }>) => void;
  debounceMs?: number;
}

export function useIntentPrefetch(text: string, opts: UseIntentPrefetchOptions) {
  const lastFired = useRef<string>('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delay = opts.debounceMs ?? DEBOUNCE_MS;
  const onPrefetch = opts.onPrefetch;

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const tickers = extractTickers(text);
      if (tickers.length === 0) return;
      const key = tickers.sort().join(',');
      if (key === lastFired.current) return;
      lastFired.current = key;
      onPrefetch({ type: 'prefetch', tickers });
    }, delay);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [text, delay, onPrefetch]);
}

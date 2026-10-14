/**
 * Response parser — bridges agent chat text → structured research panel data.
 * Detects ticker mentions, extracts JSON blocks, and hydrates the store.
 */

import { isSupported } from '../data/seedData';

/**
 * Extract ticker symbols from agent response text.
 * Matches 1-5 uppercase letter words that are in our supported list.
 */
export function extractTickers(text: string): string[] {
  const words = text.match(/\b[A-Z]{1,5}\b/g) ?? [];
  const seen = new Set<string>();
  const tickers: string[] = [];
  for (const w of words) {
    if (isSupported(w) && !seen.has(w)) {
      seen.add(w);
      tickers.push(w);
    }
  }
  return tickers;
}

/**
 * Try to extract JSON blocks from agent response text.
 * Agents sometimes return structured data embedded in their responses.
 */
export function extractJsonBlocks(text: string): Record<string, unknown>[] {
  const blocks: Record<string, unknown>[] = [];
  // Match JSON objects (greedy, nested-aware via simple brace counting)
  let depth = 0;
  let start = -1;
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '{') {
      if (depth === 0) start = i;
      depth++;
    } else if (text[i] === '}') {
      depth--;
      if (depth === 0 && start >= 0) {
        try {
          const parsed = JSON.parse(text.slice(start, i + 1));
          if (typeof parsed === 'object' && parsed !== null) {
            blocks.push(parsed as Record<string, unknown>);
          }
        } catch {
          // Not valid JSON, skip
        }
        start = -1;
      }
    }
  }
  return blocks;
}


/**
 * Detect which research tab is most relevant based on the user's query.
 */
export function detectRelevantTab(
  userQuery: string,
): 'company' | 'coverage' | 'analysis' | 'filings' | null {
  const q = userQuery.toLowerCase();
  if (q.includes('filing') || q.includes('10-k') || q.includes('10-q') || q.includes('8-k') || q.includes('sec') || q.includes('annual report')) {
    return 'filings';
  }
  if (q.includes('coverage') || q.includes('analyst') || q.includes('who covers') || q.includes('rating') || q.includes('target price') || q.includes('consensus')) {
    return 'coverage';
  }
  if (q.includes('fair value') || q.includes('dcf') || q.includes('valuation') || q.includes('comps') || q.includes('monte carlo') || q.includes('financial') || q.includes('revenue') || q.includes('earnings') || q.includes('margin')) {
    return 'analysis';
  }
  if (q.includes('tell me about') || q.includes('company') || q.includes('overview') || q.includes('what is') || q.includes('describe')) {
    return 'company';
  }
  return null;
}

/**
 * Parse a price string like "$135.40" into a number.
 */
export function parsePrice(s: string): number | null {
  const match = s.match(/\$?([\d,]+\.?\d*)/);
  if (!match) return null;
  return parseFloat(match[1].replace(/,/g, ''));
}

/**
 * Format a number as a compact dollar string (e.g., 135.4 → "$135.40").
 */
export function formatPrice(n: number): string {
  return `$${n.toFixed(2)}`;
}

/**
 * Format a percentage with sign (e.g., 17.4 → "+17.4%", -5.1 → "-5.1%").
 */
export function formatPct(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

/**
 * Calculate days until a date string (YYYY-MM-DD format).
 */
export function daysUntil(dateStr: string): number {
  const target = new Date(dateStr);
  const now = new Date();
  const diff = target.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

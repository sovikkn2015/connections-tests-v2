/**
 * Response parser — bridges agent chat text → structured research panel data.
 * Detects ticker mentions, extracts JSON blocks, and hydrates the store.
 */

import { isSupported } from '../data/seedData';

// Common English words that look like tickers but aren't
const TICKER_BLOCKLIST = new Set([
  'I', 'A', 'AM', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'HE', 'IF',
  'IN', 'IS', 'IT', 'ME', 'MY', 'NO', 'OF', 'OK', 'ON', 'OR', 'SO', 'TO',
  'UP', 'US', 'WE', 'ALL', 'AND', 'ARE', 'BUT', 'CAN', 'DID', 'FOR', 'GET',
  'GOT', 'HAS', 'HAD', 'HER', 'HIM', 'HIS', 'HOW', 'ITS', 'LET', 'MAY',
  'NEW', 'NOT', 'NOW', 'OLD', 'OUR', 'OUT', 'OWN', 'RUN', 'SAY', 'SHE',
  'THE', 'TOO', 'TWO', 'USE', 'WAY', 'WHO', 'WHY', 'YES', 'YET', 'YOU',
  'ALSO', 'BEEN', 'CALL', 'COME', 'EACH', 'FIND', 'FROM', 'GIVE', 'HAVE',
  'HERE', 'HIGH', 'JUST', 'KNOW', 'LAST', 'LIKE', 'LONG', 'LOOK', 'MADE',
  'MAKE', 'MANY', 'MORE', 'MOST', 'MUCH', 'MUST', 'NAME', 'NEXT', 'ONLY',
  'OVER', 'PART', 'SAID', 'SAME', 'SHOW', 'SIDE', 'SOME', 'SUCH', 'SURE',
  'TAKE', 'TELL', 'THAN', 'THAT', 'THEM', 'THEN', 'THEY', 'THIS', 'TIME',
  'VERY', 'WANT', 'WELL', 'WENT', 'WERE', 'WHAT', 'WHEN', 'WILL', 'WITH',
  'WORK', 'YEAR', 'YOUR', 'DEEP', 'DIVE', 'INTO', 'DOES', 'DONE',
  'SEC', 'FAQ', 'CEO', 'CFO', 'CTO', 'COO', 'IPO', 'ETF', 'GDP', 'CPI',
  'DCF', 'EPS', 'FCF', 'ROE', 'ROA', 'YOY', 'QOQ', 'TTM', 'FY', 'PE',
  'BUY', 'SELL', 'HOLD',
]);

/** Extract ticker symbols from agent response text. */
export function extractTickers(text: string): string[] {
  const words = text.match(/\b[A-Z]{1,5}\b/g) ?? [];
  const seen = new Set<string>();
  const tickers: string[] = [];
  for (const w of words) {
    if (TICKER_BLOCKLIST.has(w)) continue;
    // Known seed tickers always pass
    if (isSupported(w) && !seen.has(w)) {
      seen.add(w);
      tickers.push(w);
      continue;
    }
    // For unknown tickers: accept 2-5 char uppercase words not in blocklist
    if (w.length >= 2 && !seen.has(w)) {
      seen.add(w);
      tickers.push(w);
    }
  }
  return tickers;
}

/** Try to extract JSON blocks from agent response text. */
export function extractJsonBlocks(text: string): Record<string, unknown>[] {
  const blocks: Record<string, unknown>[] = [];
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

/** Detect which research tab is most relevant based on the user's query. */
export function detectRelevantTab(
  userQuery: string,
): 'company' | 'coverage' | 'analysis' | 'filings' | 'brief' | null {
  const q = userQuery.toLowerCase();
  if (q.includes('brief') || q.includes('prep me') || q.includes('research note') || q.includes('deep dive')) {
    return 'brief';
  }
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

/** Parse a price string like "$135.40" into a number. */
export function parsePrice(s: string): number | null {
  const match = s.match(/\$?([\d,]+\.?\d*)/);
  if (!match) return null;
  return parseFloat(match[1].replace(/,/g, ''));
}

/** Format a number as a price string. */
export function formatPrice(n: number): string {
  return `${n.toFixed(2)}`;
}

/** Format a percentage with sign. */
export function formatPct(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

/** Calculate days until a date string (YYYY-MM-DD format). */
export function daysUntil(dateStr: string): number {
  const target = new Date(dateStr);
  const now = new Date();
  const diff = target.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

/**
 * Response parser — extracts structured wealth advisor data from agent text.
 * Detects client names, parses structured summaries, and routes to tabs.
 */

import type { AdvisorTab } from '../types';

/** Extract a likely client/household name from agent response text. */
export function extractClientName(text: string): string | null {
  const patterns = [
    /(?:about|for|viewing|discussing|client|household)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/i,
    /([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:household|family|portfolio|account)/i,
    /(?:^|\n)\s*(?:Client|Household|Name):\s*(.+)/im,
  ];
  for (const p of patterns) {
    const m = text.match(p);
    if (m?.[1]) return m[1].trim();
  }
  return null;
}

/** Detect which advisor tab is most relevant based on the user query. */
export function detectRelevantTab(userQuery: string): AdvisorTab | null {
  const q = userQuery.toLowerCase();
  if (q.includes('portfolio') || q.includes('allocation') || q.includes('performance') || q.includes('return') || q.includes('rebalanc') || q.includes('drift')) return 'portfolio';
  if (q.includes('goal') || q.includes('retirement') || q.includes('college') || q.includes('target') || q.includes('saving') || q.includes('progress')) return 'goals';
  if (q.includes('meeting') || q.includes('prep') || q.includes('transaction') || q.includes('trade') || q.includes('compliance') || q.includes('referral') || q.includes('activity')) return 'activity';
  if (q.includes('tell me about') || q.includes('who is') || q.includes('look up') || q.includes('client') || q.includes('household') || q.includes('family')) return 'clients';
  return null;
}

/** Format a percentage with sign. */
export function formatPct(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

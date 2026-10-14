/**
 * Response parser — bridges agent chat text → structured research panel data.
 * Detects ticker mentions, extracts JSON blocks, and hydrates the store.
 */

/* ── Company name → ticker mapping ── */
const COMPANY_TO_TICKER: Record<string, string> = {
  APPLE: 'AAPL',
  MICROSOFT: 'MSFT',
  NVIDIA: 'NVDA',
  AMAZON: 'AMZN',
  ALPHABET: 'GOOGL',
  GOOGLE: 'GOOGL',
  JPMORGAN: 'JPM',
  CHASE: 'JPM',
  VISA: 'V',
  JOHNSON: 'JNJ',
  EXXONMOBIL: 'XOM',
  EXXON: 'XOM',
  TESLA: 'TSLA',
  SALESFORCE: 'CRM',
};

/* ── Common English words that should never be treated as tickers ── */
const STOP_WORDS = new Set([
  'A', 'I', 'AM', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'IF', 'IN',
  'IS', 'IT', 'ME', 'MY', 'NO', 'OF', 'OK', 'ON', 'OR', 'SO', 'TO', 'UP',
  'US', 'WE', 'ALL', 'AND', 'ANY', 'ARE', 'BUT', 'CAN', 'DID', 'FOR',
  'GET', 'GOT', 'HAS', 'HAD', 'HER', 'HIM', 'HIS', 'HOW', 'ITS', 'LET',
  'MAY', 'NEW', 'NOT', 'NOW', 'OLD', 'OUR', 'OUT', 'OWN', 'RUN', 'SAY',
  'SHE', 'THE', 'TOO', 'TRY', 'USE', 'WAS', 'WAY', 'WHO', 'WHY', 'WIN',
  'WON', 'YET', 'YOU', 'ALSO', 'BEEN', 'COME', 'DOES', 'EACH', 'EVEN',
  'FIND', 'FROM', 'GIVE', 'GOOD', 'HAVE', 'HERE', 'HIGH', 'JUST', 'KNOW',
  'LAST', 'LIKE', 'LONG', 'LOOK', 'MADE', 'MAKE', 'MANY', 'MORE', 'MOST',
  'MUCH', 'MUST', 'NEED', 'NEXT', 'ONLY', 'OVER', 'PART', 'SAME', 'SHOW',
  'SOME', 'SUCH', 'TAKE', 'TELL', 'THAN', 'THAT', 'THEM', 'THEN', 'THEY',
  'THIS', 'TIME', 'VERY', 'WANT', 'WELL', 'WERE', 'WHAT', 'WHEN', 'WILL',
  'WITH', 'WORK', 'YEAR', 'YOUR', 'ABOUT', 'AFTER', 'BEING', 'COULD',
  'EVERY', 'FIRST', 'GREAT', 'MIGHT', 'OTHER', 'PRICE', 'RIGHT', 'SHALL',
  'SHOULD', 'SINCE', 'STILL', 'THEIR', 'THERE', 'THESE', 'THINK', 'THOSE',
  'THREE', 'TODAY', 'UNDER', 'USING', 'VALUE', 'WATCH', 'WATER', 'WHATS',
  'WHERE', 'WHICH', 'WHILE', 'WORLD', 'WOULD', 'STOCK', 'TRADE', 'TRADING',
  'DCF', 'COMPS', 'MONTE', 'CARLO', 'FAIR', 'RUN', 'SEC', 'EDGAR',
  'NEWS', 'TONE', 'CALL', 'QUOTE', 'FILED', 'ANNUAL', 'FILING',
]);


/**
 * Check if a string looks like a valid ticker symbol:
 * 1-5 uppercase letters that aren't common English stop words.
 */
function isValidTicker(t: string): boolean {
  return /^[A-Z]{1,5}$/.test(t) && !STOP_WORDS.has(t);
}

/**
 * Extract ticker symbols from user query text.
 *
 * Strategy:
 *  1. Strip possessives / contractions (What's → What)
 *  2. Match known company names (case-insensitive) → resolve to ticker
 *  3. Match uppercase 1-5 letter words that look like valid tickers
 *  4. Filter out common English stop-words to avoid false positives
 */
export function extractTickers(text: string): string[] {
  const seen = new Set<string>();
  const tickers: string[] = [];

  const addTicker = (t: string) => {
    if (!seen.has(t)) {
      seen.add(t);
      tickers.push(t);
    }
  };

  const upper = text.toUpperCase();

  // 1. Check for company name matches (longest first to prefer multi-word names)
  const sortedNames = Object.keys(COMPANY_TO_TICKER).sort(
    (a, b) => b.length - a.length,
  );
  for (const name of sortedNames) {
    if (upper.includes(name)) {
      const ticker = COMPANY_TO_TICKER[name];
      if (isValidTicker(ticker)) addTicker(ticker);
    }
  }

  // 2. Strip possessives / contractions, then match uppercase words
  const cleaned = upper.replace(/['']/g, ' ');
  const words = cleaned.match(/\b[A-Z]{1,5}\b/g) ?? [];
  for (const w of words) {
    if (!STOP_WORDS.has(w) && isValidTicker(w)) {
      addTicker(w);
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
  return `${n.toFixed(2)}`;
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

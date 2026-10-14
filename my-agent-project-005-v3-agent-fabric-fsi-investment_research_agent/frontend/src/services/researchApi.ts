/**
 * researchApi.ts — Fetches structured data for the research panel.
 *
 * ALL calls go through Salesforce Apex InvocableActions (same as chat).
 * This avoids CORS issues with direct AWS API Gateway calls.
 * Apex actions call AWS Lambda server-side and return text responses.
 * We parse the text into typed structures for the research panel.
 */

import type {
  CompanyData,
  CoverageData,
  ConsensusSummary,
  ValuationData,
  SentimentData,
  FilingData,
} from '../types';

// ── Config ──

const API_VERSION = 'v66.0';

// ── Salesforce Apex action caller ──

function sfHeaders(accessToken: string): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
}

async function callApexAction(
  accessToken: string,
  instanceUrl: string,
  actionName: string,
  inputKey: string,
  inputValue: string,
): Promise<string> {
  const url = `${instanceUrl}/services/data/${API_VERSION}/actions/custom/apex/${actionName}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: sfHeaders(accessToken),
    body: JSON.stringify({ inputs: [{ [inputKey]: inputValue }] }),
  });
  if (!res.ok) throw new Error(`Apex ${actionName}: ${res.status}`);
  const data = await res.json();
  const result = data[0];
  if (!result?.isSuccess) throw new Error(result?.errors?.[0]?.message || 'Action failed');
  const outputs = result.outputValues || {};
  return String(Object.values(outputs).find((v) => v != null && v !== '') ?? '');
}

// ── Parsers ──

function getField(text: string, label: string): string {
  const re = new RegExp(label + ':\\s*(.+)', 'i');
  return re.exec(text)?.[1]?.trim() ?? '';
}

function parseCompanyLookup(text: string): Partial<CompanyData> {
  const earningsRaw = getField(text, 'Next Earnings');
  return {
    name: getField(text, 'Company'),
    ticker: getField(text, 'Ticker'),
    sector: getField(text, 'Sector'),
    exchange: getField(text, 'Exchange'),
    marketCap: getField(text, 'Market Cap'),
    earningsDate: earningsRaw.replace(/\s*\(.*\)/, '').trim(),
  };
}

function parseQuoteResponse(text: string): { price: number; change: number; changePct: number } {
  const priceMatch = text.match(/Price:\s*\$?([\d.]+)/i);
  const changeMatch = text.match(/Change:\s*(-?[\d.]+)\s*\((-?[\d.]+)%?\)/i);
  return {
    price: priceMatch ? parseFloat(priceMatch[1]) : 0,
    change: changeMatch ? parseFloat(changeMatch[1]) : 0,
    changePct: changeMatch ? parseFloat(changeMatch[2]) : 0,
  };
}

/**
 * Parse IR_MarketDataAction output when called with "analyst consensus" query.
 * Format:
 *   NVDA Analyst Consensus:
 *     Target Price: $...
 *     P/E Ratio: 65.43
 *     Forward P/E: 45.12
 *     EPS: $3.08
 *     Profit Margin: 0.5593
 *     Beta: 1.68
 *     52W Range: $86.62 - $974.00
 */
function parseConsensusResponse(text: string): {
  peRatio: string; forwardPE: string; eps: string; profitMargin: string;
  beta: string; weekHigh52: string; weekLow52: string;
} {
  const f = (label: string) => {
    const re = new RegExp(label + ':\\s*\\$?([^\\n]+)', 'i');
    return re.exec(text)?.[1]?.trim() ?? '';
  };
  const pe = f('P/E Ratio');
  const fpe = f('Forward P/E');
  const eps = f('EPS');
  const margin = f('Profit Margin');
  const beta = f('Beta');
  const rangeMatch = text.match(/52W Range:\s*\$?([\d.]+)\s*-\s*\$?([\d.]+)/i);

  const fmtPct = (raw: string) => {
    const n = parseFloat(raw);
    if (isNaN(n)) return '—';
    // Alpha Vantage returns profit margin as decimal (0.5593 = 55.93%)
    return (n <= 1 ? n * 100 : n).toFixed(2) + '%';
  };
  const fmtNum = (raw: string, decimals = 2) => {
    const n = parseFloat(raw);
    return isNaN(n) ? '—' : n.toFixed(decimals);
  };
  const fmtMoney = (raw: string) => {
    const n = parseFloat(raw);
    return isNaN(n) ? '—' : `$${n.toFixed(2)}`;
  };

  return {
    peRatio: pe ? fmtNum(pe) : '—',
    forwardPE: fpe ? fmtNum(fpe) : '—',
    eps: eps ? fmtMoney(eps) : '—',
    profitMargin: margin ? fmtPct(margin) : '—',
    beta: beta ? fmtNum(beta) : '—',
    weekHigh52: rangeMatch ? `$${parseFloat(rangeMatch[2]).toFixed(2)}` : '—',
    weekLow52: rangeMatch ? `$${parseFloat(rangeMatch[1]).toFixed(2)}` : '—',
  };
}

/**
 * Parse IR_MarketDataAction output when called with "options chain" query.
 * Returns 50D/200D moving averages.
 */
function parseOptionsResponse(text: string): {
  movingAvg50: string; movingAvg200: string;
} {
  const f = (label: string) => {
    const re = new RegExp(label + ':\\s*\\$?([^\\n]+)', 'i');
    return re.exec(text)?.[1]?.trim() ?? '';
  };
  const ma50 = f('50D MA');
  const ma200 = f('200D MA');
  const fmt = (raw: string) => {
    const n = parseFloat(raw);
    return isNaN(n) ? '—' : `$${n.toFixed(2)}`;
  };
  return {
    movingAvg50: ma50 ? fmt(ma50) : '—',
    movingAvg200: ma200 ? fmt(ma200) : '—',
  };
}

type RatingType = 'Buy' | 'Hold' | 'Sell' | 'Overweight' | 'Underweight';

function normalizeRating(raw: string): RatingType {
  const l = raw.toLowerCase();
  if (l === 'buy') return 'Buy';
  if (l === 'overweight') return 'Overweight';
  if (l === 'sell') return 'Sell';
  if (l === 'underweight') return 'Underweight';
  return 'Hold';
}

function parseCoverageRows(text: string): CoverageData[] {
  const rows: CoverageData[] = [];
  const re = /^(.+?)\s*\|\s*.+?\(.*?\)\s*\|\s*Rating:\s*(\w+)\s*\|\s*Target:\s*\$?([\d,.]+)\s*\|\s*Updated:\s*(.+)$/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    rows.push({
      analyst: m[1].trim(),
      firm: '',
      rating: normalizeRating(m[2].trim()),
      targetPrice: `$${m[3].trim()}`,
      lastUpdated: m[4].trim(),
    });
  }
  return rows;
}

function computeConsensus(coverage: CoverageData[], currentPrice: number): ConsensusSummary {
  let buyCount = 0, holdCount = 0, sellCount = 0;
  const targets: number[] = [];
  for (const c of coverage) {
    if (c.rating === 'Buy' || c.rating === 'Overweight') buyCount++;
    else if (c.rating === 'Hold') holdCount++;
    else sellCount++;
    const n = parseFloat(c.targetPrice.replace(/[$,]/g, ''));
    if (!isNaN(n)) targets.push(n);
  }
  const avg = targets.length ? targets.reduce((a, b) => a + b, 0) / targets.length : 0;
  return {
    buyCount, holdCount, sellCount,
    avgTargetPrice: Math.round(avg * 100) / 100,
    highTargetPrice: targets.length ? Math.max(...targets) : 0,
    lowTargetPrice: targets.length ? Math.min(...targets) : 0,
    currentPrice,
  };
}

function parseValuationResponse(text: string): ValuationData | null {
  const dcfMatch = text.match(/(?:DCF\s+)?Fair Value:\s*\$?([\d.]+)/i);
  const mcMatch = text.match(/Monte Carlo Median:\s*\$?([\d.]+)/i);
  const priceMatch = text.match(/Current Price:\s*\$?([\d.]+)/i);
  const p5Match = text.match(/5th Percentile:\s*\$?([\d.]+)/i);
  const p95Match = text.match(/95th Percentile:\s*\$?([\d.]+)/i);
  const peMatch = text.match(/P\/E vs Peers:\s*(.+)/i);
  const evMatch = text.match(/EV\/EBITDA vs Peers:\s*(.+)/i);
  const psMatch = text.match(/P\/S vs Peers:\s*(.+)/i);

  const dcf = dcfMatch ? parseFloat(dcfMatch[1]) : 0;
  const currentPrice = priceMatch ? parseFloat(priceMatch[1]) : 0;
  if (dcf === 0 && currentPrice === 0) return null;

  const upsidePct = currentPrice > 0 ? Math.round(((dcf - currentPrice) / currentPrice) * 10000) / 100 : 0;

  return {
    dcfFairValue: dcf,
    currentPrice,
    upsidePct,
    monteCarloMedian: mcMatch ? parseFloat(mcMatch[1]) : 0,
    monteCarloP5: p5Match ? parseFloat(p5Match[1]) : 0,
    monteCarloP95: p95Match ? parseFloat(p95Match[1]) : 0,
    compsRelativeValuation: {
      peVsPeers: peMatch?.[1]?.trim() ?? '—',
      evEbitdaVsPeers: evMatch?.[1]?.trim() ?? '—',
      psVsPeers: psMatch?.[1]?.trim() ?? '—',
    },
    peers: [],
    narrative: text,
  };
}

function parseSentimentResponse(text: string): SentimentData | null {
  const sentMatch = text.match(/(?:Overall\s+)?Sentiment:\s*(\w+)/i);
  const confMatch = text.match(/Confidence:\s*(\w+)/i);
  const summaryMatch = text.match(/Summary:\s*(.+)/i);
  const recoMatch = text.match(/Recommendation:\s*(.+)/i);

  if (!sentMatch) return null;

  const raw = sentMatch[1];
  const overallSentiment = raw.toLowerCase().includes('bull') ? 'Bullish' as const
    : raw.toLowerCase().includes('bear') ? 'Bearish' as const : 'Neutral' as const;
  const confidence = confMatch?.[1]?.toLowerCase().includes('high') ? 'High' as const
    : confMatch?.[1]?.toLowerCase().includes('low') ? 'Low' as const : 'Medium' as const;

  return {
    overallSentiment,
    confidence,
    sentimentScore: overallSentiment === 'Bullish' ? 0.75 : overallSentiment === 'Bearish' ? 0.25 : 0.5,
    keyDrivers: [summaryMatch?.[1] ?? recoMatch?.[1] ?? 'See chat for details'].filter(Boolean),
    transcriptSentiment: raw,
    newsSentiment: raw,
  };
}

function parseFilingsResponse(text: string): FilingData[] {
  const filings: FilingData[] = [];
  const re = /- (10-K|10-Q|8-K|\S+)\s*\|\s*Filed:\s*([\d-]+)\s*\|\s*(.+)/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    filings.push({
      type: m[1].trim(),
      date: m[2].trim(),
      description: m[3].trim(),
      url: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=${m[1].trim()}`,
    });
  }
  return filings;
}

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC API — all through Salesforce Apex (no CORS issues)
// ═══════════════════════════════════════════════════════════════════════════

export async function fetchCompanyData(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<CompanyData | null> {
  try {
    const [companyText, quoteText, consensusText, optionsText] = await Promise.all([
      callApexAction(accessToken, instanceUrl, 'IR_CompanyLookupAction', 'companyName', ticker).catch(() => ''),
      callApexAction(accessToken, instanceUrl, 'IR_MarketDataAction', 'query', `${ticker} quote`).catch(() => ''),
      callApexAction(accessToken, instanceUrl, 'IR_MarketDataAction', 'query', `${ticker} analyst consensus`).catch(() => ''),
      callApexAction(accessToken, instanceUrl, 'IR_MarketDataAction', 'query', `${ticker} options chain`).catch(() => ''),
    ]);

    const crm = parseCompanyLookup(companyText);
    const quote = parseQuoteResponse(quoteText);
    const consensus = parseConsensusResponse(consensusText);
    const options = parseOptionsResponse(optionsText);
    const name = crm.name || ticker;
    const sector = crm.sector || 'Unknown';
    const exchange = crm.exchange || 'Unknown';

    return {
      name,
      ticker: crm.ticker || ticker.toUpperCase(),
      sector,
      exchange,
      marketCap: crm.marketCap || '—',
      peRatio: consensus.peRatio,
      earningsDate: crm.earningsDate || '—',
      weekHigh52: consensus.weekHigh52,
      weekLow52: consensus.weekLow52,
      description: `${name} is a ${sector} company listed on ${exchange}.`,
      industry: sector,
      price: quote.price,
      change: quote.change,
      changePct: quote.changePct,
      beta: consensus.beta,
      dividendYield: '—',
      forwardPE: consensus.forwardPE,
      profitMargin: consensus.profitMargin,
      epsttm: consensus.eps,
      revenuePerShare: '—',
      movingAvg50: options.movingAvg50,
      movingAvg200: options.movingAvg200,
    };
  } catch (err) {
    console.warn('[researchApi] fetchCompanyData failed:', err);
    return null;
  }
}

export async function fetchCoverageData(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<{ coverage: CoverageData[]; consensus: ConsensusSummary } | null> {
  try {
    const text = await callApexAction(accessToken, instanceUrl, 'IR_CoverageCheckAction', 'query', ticker);
    const coverage = parseCoverageRows(text);
    const currentPrice = 0; // will be updated by company data
    return { coverage, consensus: computeConsensus(coverage, currentPrice) };
  } catch (err) {
    console.warn('[researchApi] fetchCoverageData failed:', err);
    return null;
  }
}

export async function fetchValuationData(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<ValuationData | null> {
  try {
    const text = await callApexAction(accessToken, instanceUrl, 'IR_FinancialAnalysisAction', 'query', `${ticker} fair value`);
    return parseValuationResponse(text);
  } catch (err) {
    console.warn('[researchApi] fetchValuationData failed:', err);
    return null;
  }
}

export async function fetchSentimentData(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<SentimentData | null> {
  try {
    const text = await callApexAction(accessToken, instanceUrl, 'IR_SentimentAnalysisAction', 'query', `${ticker} sentiment`);
    return parseSentimentResponse(text);
  } catch (err) {
    console.warn('[researchApi] fetchSentimentData failed:', err);
    return null;
  }
}

export async function fetchFilings(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<FilingData[]> {
  try {
    const text = await callApexAction(accessToken, instanceUrl, 'IR_SecFilingsAction', 'query', `${ticker} 10-K`);
    return parseFilingsResponse(text);
  } catch (err) {
    console.warn('[researchApi] fetchFilings failed:', err);
    return [];
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MASTER FETCH — calls everything in parallel via Apex
// ═══════════════════════════════════════════════════════════════════════════

export interface AllResearchData {
  company: CompanyData | null;
  coverage: CoverageData[] | null;
  consensus: ConsensusSummary | null;
  valuation: ValuationData | null;
  sentiment: SentimentData | null;
  filings: FilingData[] | null;
}

export async function fetchAllResearchData(
  accessToken: string, instanceUrl: string, ticker: string,
): Promise<AllResearchData> {
  // Company + coverage + filings are fast (CRM only, ~1s)
  // Valuation + sentiment are slow (AWS Bedrock, ~5-30s)
  const [companyR, coverageR, filingsR, valuationR, sentimentR] = await Promise.allSettled([
    fetchCompanyData(accessToken, instanceUrl, ticker),
    fetchCoverageData(accessToken, instanceUrl, ticker),
    fetchFilings(accessToken, instanceUrl, ticker),
    fetchValuationData(accessToken, instanceUrl, ticker),
    fetchSentimentData(accessToken, instanceUrl, ticker),
  ]);

  const company = companyR.status === 'fulfilled' ? companyR.value : null;
  const coverageBundle = coverageR.status === 'fulfilled' ? coverageR.value : null;
  const valuation = valuationR.status === 'fulfilled' ? valuationR.value : null;
  const sentiment = sentimentR.status === 'fulfilled' ? sentimentR.value : null;
  const filings = filingsR.status === 'fulfilled' ? filingsR.value : null;

  return {
    company,
    coverage: coverageBundle?.coverage ?? null,
    consensus: coverageBundle?.consensus ?? null,
    valuation,
    sentiment,
    filings: filings && filings.length > 0 ? filings : null,
  };
}

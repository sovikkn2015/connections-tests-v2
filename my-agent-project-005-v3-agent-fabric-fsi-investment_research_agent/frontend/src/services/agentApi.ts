/**
 * Salesforce Agent API client with Apex Invocable Action fallback.
 *
 * V3 Agent Fabric additions (non-breaking vs V2):
 *  • Every outbound gateway call carries:
 *      - X-Correlation-Id (UUIDv4, thread-scoped so follow-ups share an ID)
 *        — required by finra-audit policy.
 *      - X-Agent-Id (default: `ir-research-orchestrator`)
 *        — required by rate-limit policy to bucket by caller.
 *  • When VITE_FLEX_GATEWAY_URL is set, API Gateway-bound calls route through
 *    the Flex Gateway ALB. When unset, the V2 direct-to-API-Gateway path is
 *    preserved (this keeps the V2/V3 comparison the EVAL subagent depends on
 *    and provides a clean rollback lever).
 *
 * Agent API (api.salesforce.com) continues to use an ECA token from the
 * token proxy Lambda. Apex fallbacks continue to use the user's PKCE token.
 */

const API_VERSION = 'v66.0';
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || '';
const FLEX_GATEWAY_URL = import.meta.env.VITE_FLEX_GATEWAY_URL || '';
const AGENT_ID_HEADER = import.meta.env.VITE_AGENT_ID || 'ir-research-orchestrator';

/* ── Agent API (api.salesforce.com) ── */

const AGENT_API_BASE = 'https://api.salesforce.com/einstein/ai-agent/v1';

/* ── V3: Correlation ID lifecycle ──
 *
 * A single correlationId covers a "thread" — one user → agent conversation —
 * so every Flex Gateway audit row for that thread can be grouped (finra-audit
 * policy relies on this). The ID is regenerated on startSession() and reset on
 * endSession(), and cached in sessionStorage so a page reload mid-thread
 * keeps the same ID.
 */
const CORRELATION_KEY = 'ir-correlation-id';

function getCorrelationId(): string {
  try {
    const existing = sessionStorage.getItem(CORRELATION_KEY);
    if (existing) return existing;
  } catch {
    /* sessionStorage unavailable (private mode) — fall through */
  }
  const fresh = crypto.randomUUID();
  try {
    sessionStorage.setItem(CORRELATION_KEY, fresh);
  } catch {
    /* ignore write failures */
  }
  return fresh;
}

function rotateCorrelationId(): string {
  const fresh = crypto.randomUUID();
  try {
    sessionStorage.setItem(CORRELATION_KEY, fresh);
  } catch {
    /* ignore */
  }
  return fresh;
}

function clearCorrelationId(): void {
  try {
    sessionStorage.removeItem(CORRELATION_KEY);
  } catch {
    /* ignore */
  }
}

/** Headers used for Salesforce-flavoured calls (Agent API + Apex). */
function headers(accessToken: string, accept = 'application/json'): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    Accept: accept,
    'X-Correlation-Id': getCorrelationId(),
    'X-Agent-Id': AGENT_ID_HEADER,
  };
}

/**
 * Returns the base URL for calls that go through the V3 Flex Gateway when
 * configured, otherwise falls back to the V2 direct API Gateway URL.
 * Exported so the rest of the app (and tests) can reason about the active path.
 */
export function getGatewayBaseUrl(): string {
  return FLEX_GATEWAY_URL || API_GATEWAY_URL;
}

export function isFlexGatewayActive(): boolean {
  return Boolean(FLEX_GATEWAY_URL);
}

/* ── ECA token cache — separate from the PKCE token ── */

let _ecaToken: string | null = null;
let _ecaTokenExpiry = 0;

async function getEcaToken(): Promise<string> {
  if (_ecaToken && Date.now() < _ecaTokenExpiry) return _ecaToken;
  // Token proxy runs on the original API Gateway (OAuth concerns stay on AWS,
  // not the Flex Gateway). V3 intentionally keeps this on API_GATEWAY_URL.
  const res = await fetch(`${API_GATEWAY_URL}/oauth/agent-token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-Id': getCorrelationId(),
      'X-Agent-Id': AGENT_ID_HEADER,
    },
  });
  if (!res.ok) throw new Error(`ECA token failed: ${res.status}`);
  const data = await res.json();
  _ecaToken = data.access_token;
  _ecaTokenExpiry = Date.now() + 7000 * 1000;
  return _ecaToken!;
}

/**
 * Try the real Agent API first. If it fails, fall back to Apex actions.
 * Rotates the correlation ID so each new session starts a fresh audit thread.
 */
export async function startSession(
  accessToken: string,
  instanceUrl: string,
  agentId: string,
): Promise<string> {
  rotateCorrelationId();
  try {
    const sessionId = await startAgentApiSession(accessToken, instanceUrl, agentId);
    return sessionId;
  } catch {
    console.info('[AgentAPI] Agent API unavailable, using Apex action fallback');
    return startApexFallbackSession();
  }
}

async function startAgentApiSession(
  _accessToken: string,
  instanceUrl: string,
  agentId: string,
): Promise<string> {
  const ecaToken = await getEcaToken();
  const uuid = crypto.randomUUID();
  const res = await fetch(`${AGENT_API_BASE}/agents/${agentId}/sessions`, {
    method: 'POST',
    headers: headers(ecaToken),
    body: JSON.stringify({
      externalSessionKey: uuid,
      instanceConfig: { endpoint: instanceUrl },
      streamingCapabilities: { chunkTypes: ['Text'] },
      bypassUser: true,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Agent API session failed: ${res.status} — ${err}`);
  }
  const data = await res.json();
  return data.sessionId;
}

function startApexFallbackSession(): string {
  return `apex-fallback-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/* ── Apex Action routing ── */

interface ActionRoute {
  action: string;
  inputKey: string;
  outputKey: string;
}

function routeMessage(text: string): ActionRoute {
  const lower = text.toLowerCase();

  if (lower.includes('filing') || lower.includes('10-k') || lower.includes('10-q') || lower.includes('sec')) {
    return { action: 'IR_SecFilingsAction', inputKey: 'query', outputKey: 'filingInfo' };
  }
  if (lower.includes('coverage') || lower.includes('analyst') || lower.includes('who covers') || lower.includes('rating')) {
    return { action: 'IR_CoverageCheckAction', inputKey: 'query', outputKey: 'coverageInfo' };
  }
  if (lower.includes('earnings') || lower.includes('calendar') || lower.includes('report')) {
    return { action: 'IR_EarningsCalendarAction', inputKey: 'query', outputKey: 'earningsCalendar' };
  }
  if (lower.includes('watchlist')) {
    return { action: 'IR_WatchlistAction', inputKey: 'query', outputKey: 'watchlistInfo' };
  }
  if (lower.includes('compliance') || lower.includes('trade') || lower.includes('restricted')) {
    return { action: 'IR_ComplianceScreeningAction', inputKey: 'ticker', outputKey: 'complianceResult' };
  }
  if (lower.includes('market data') || lower.includes('price') || lower.includes('quote') || lower.includes('trading at')) {
    return { action: 'IR_MarketDataAction', inputKey: 'query', outputKey: 'marketData' };
  }
  if (lower.includes('news') || lower.includes('headline')) {
    return { action: 'IR_NewsSearchAction', inputKey: 'query', outputKey: 'newsResults' };
  }
  if (lower.includes('sentiment') || lower.includes('tone') || lower.includes('feeling')) {
    return { action: 'IR_SentimentAnalysisAction', inputKey: 'query', outputKey: 'sentimentResult' };
  }
  if (lower.includes('fair value') || lower.includes('dcf') || lower.includes('valuation') || lower.includes('comps') || lower.includes('monte carlo')) {
    return { action: 'IR_FinancialAnalysisAction', inputKey: 'query', outputKey: 'analysisResult' };
  }
  return { action: 'IR_CompanyLookupAction', inputKey: 'companyName', outputKey: 'companyInfo' };
}

function extractCompanyTerm(text: string): string {
  const cleaned = text
    .replace(/^(show me|look up|get|find|search|tell me about|tell more about|tell us about|what is|what's|what about|describe|explain|give me|info on|details on|details about|more about|about)\s+/i, '')
    .replace(/\s+(company|info|data|details|coverage|filings|earnings|news|sentiment|analysis|financials|10-k|10-q|sec)\b.*/i, '')
    .trim();

  if (cleaned.includes(' ') || cleaned.length > 10) {
    const words = text.split(/\s+/);
    for (const word of words) {
      const upper = word.replace(/[^A-Za-z]/g, '').toUpperCase();
      if (upper.length >= 1 && upper.length <= 5 && !isCommonWord(upper)) {
        return upper;
      }
    }
  }
  return cleaned || text.trim();
}

function isCommonWord(word: string): boolean {
  const common = new Set([
    'THE', 'AND', 'FOR', 'CAN', 'SHOW', 'TELL', 'WHAT', 'WHO', 'WHEN', 'HOW',
    'GET', 'FIND', 'ME', 'MY', 'IS', 'ON', 'IN', 'AT', 'TO', 'OF', 'ABOUT',
    'DOES', 'TRADE', 'LATEST', 'MORE', 'GIVE', 'ALL', 'YOU', 'YOUR', 'SOME',
    'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'HAS', 'NOT', 'BUT', 'ARE', 'WAS',
  ]);
  return common.has(word);
}

function getInputValue(text: string, inputKey: string): string {
  if (inputKey === 'query') return text;
  if (inputKey === 'ticker') {
    const words = text.split(/\s+/);
    for (const word of words) {
      const cleaned = word.replace(/[^A-Za-z]/g, '').toUpperCase();
      if (cleaned.length >= 1 && cleaned.length <= 5 && !isCommonWord(cleaned)) {
        return cleaned;
      }
    }
    return text;
  }
  return extractCompanyTerm(text);
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
    headers: headers(accessToken),
    body: JSON.stringify({ inputs: [{ [inputKey]: inputValue }] }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Apex action ${actionName} failed: ${res.status} — ${err}`);
  }
  const data = await res.json();
  const result = data[0];
  if (!result?.isSuccess) {
    const errMsg = result?.errors?.map((e: { message: string }) => e.message).join(', ') || 'Unknown error';
    throw new Error(`Action failed: ${errMsg}`);
  }
  const outputs = result.outputValues || {};
  const outputText = Object.values(outputs).find((v) => v != null && v !== '');
  return String(outputText ?? 'No results found.');
}

/* ── Public API ── */

export async function sendMessage(
  accessToken: string,
  instanceUrl: string,
  sessionId: string,
  message: string,
  sequenceId: number,
): Promise<string> {
  if (sessionId.startsWith('apex-fallback-')) {
    return sendApexFallbackMessage(accessToken, instanceUrl, message);
  }
  return sendAgentApiMessage(accessToken, sessionId, message, sequenceId);
}

async function sendAgentApiMessage(
  _accessToken: string,
  sessionId: string,
  message: string,
  sequenceId: number,
): Promise<string> {
  const ecaToken = await getEcaToken();
  const res = await fetch(`${AGENT_API_BASE}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: headers(ecaToken),
    body: JSON.stringify({ message: { type: 'Text', text: message, sequenceId } }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to send message: ${res.status} — ${err}`);
  }
  const data = await res.json();
  const parts: string[] = (data.messages ?? []).map((m: { message?: string; text?: string }) => m.message ?? m.text ?? '');
  return parts.join('\n').trim();
}

async function sendApexFallbackMessage(
  accessToken: string,
  instanceUrl: string,
  message: string,
): Promise<string> {
  const route = routeMessage(message);
  const inputValue = getInputValue(message, route.inputKey);
  return callApexAction(accessToken, instanceUrl, route.action, route.inputKey, inputValue);
}

export async function sendStreamingMessage(
  accessToken: string,
  instanceUrl: string,
  sessionId: string,
  message: string,
  sequenceId: number,
  onChunk: (text: string) => void,
  onComplete?: (fullText: string) => void,
): Promise<void> {
  if (sessionId.startsWith('apex-fallback-')) {
    return sendApexFallbackStreaming(accessToken, instanceUrl, message, onChunk, onComplete);
  }
  return sendAgentApiStreaming(accessToken, sessionId, message, sequenceId, onChunk, onComplete);
}

async function sendAgentApiStreaming(
  _accessToken: string,
  sessionId: string,
  message: string,
  sequenceId: number,
  onChunk: (text: string) => void,
  onComplete?: (fullText: string) => void,
): Promise<void> {
  const ecaToken = await getEcaToken();
  const res = await fetch(`${AGENT_API_BASE}/sessions/${sessionId}/messages/stream`, {
    method: 'POST',
    headers: headers(ecaToken, 'text/event-stream'),
    body: JSON.stringify({ message: { type: 'Text', text: message, sequenceId } }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Streaming failed: ${res.status} — ${err}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body for streaming');

  const decoder = new TextDecoder();
  let fullText = '';
  let sawTextChunk = false;
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() ?? '';

    for (const rawEvent of events) {
      if (!rawEvent.trim()) continue;

      let eventType = '';
      const dataLines: string[] = [];
      for (const line of rawEvent.split(/\r?\n/)) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      const dataStr = dataLines.join('\n');
      if (!dataStr) continue;

      if (eventType === 'END_OF_TURN' || dataStr === '[DONE]') {
        onComplete?.(fullText);
        return;
      }

      let parsed: { message?: { type?: string; message?: string; text?: string } } | null = null;
      try {
        parsed = JSON.parse(dataStr);
      } catch {
        continue;
      }

      const inner = parsed?.message;
      const innerType = inner?.type;
      const text = inner?.message ?? inner?.text ?? '';

      if (eventType === 'TEXT_CHUNK' || innerType === 'TextChunk') {
        if (text) {
          sawTextChunk = true;
          fullText += text;
          onChunk(text);
        }
      } else if (eventType === 'INFORM' || innerType === 'Inform') {
        if (!sawTextChunk && text) {
          fullText = text;
          onChunk(text);
        }
      }
    }
  }
  onComplete?.(fullText);
}

async function sendApexFallbackStreaming(
  accessToken: string,
  instanceUrl: string,
  message: string,
  onChunk: (text: string) => void,
  onComplete?: (fullText: string) => void,
): Promise<void> {
  const fullText = await sendApexFallbackMessage(accessToken, instanceUrl, message);

  const words = fullText.split(/(\s+)/);
  const BATCH = 3;
  for (let i = 0; i < words.length; i += BATCH) {
    const batch = words.slice(i, i + BATCH).join('');
    onChunk(batch);
    await new Promise((r) => setTimeout(r, 15));
  }
  onComplete?.(fullText);
}

export async function endSession(
  _accessToken: string,
  _instanceUrl: string,
  sessionId: string,
): Promise<void> {
  if (sessionId.startsWith('apex-fallback-')) {
    clearCorrelationId();
    return;
  }
  const ecaToken = await getEcaToken();
  const res = await fetch(`${AGENT_API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: headers(ecaToken),
  });
  clearCorrelationId();
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to end session: ${res.status} — ${err}`);
  }
}

/* ── V3 test helpers: exported for unit tests + visualizerApi ── */
export const __internal = {
  getCorrelationId,
  rotateCorrelationId,
  clearCorrelationId,
  getGatewayBaseUrl,
  isFlexGatewayActive,
};

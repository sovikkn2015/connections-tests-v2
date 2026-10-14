/**
 * Salesforce Agent API client with Apex Invocable Action fallback.
 *
 * The Agent API (api.salesforce.com/einstein/ai-agent/v1) requires an ECA
 * (External Client App) token with `chatbot_api` scope. The PKCE token from
 * the Connected App only has `api` scope, so we mint a separate ECA token
 * via the token proxy Lambda for Agent API calls.
 *
 * - Agent API calls → ECA token (from /oauth/agent-token)
 * - Apex fallback calls → PKCE token (from login flow, unchanged)
 *
 * Fallback endpoint: /services/data/v66.0/actions/custom/apex/{ActionName}
 */

const API_VERSION = 'v66.0';
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || '';

/* ── Agent API (api.salesforce.com) ── */

const AGENT_API_BASE = 'https://api.salesforce.com/einstein/ai-agent/v1';

function headers(accessToken: string, accept = 'application/json'): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    Accept: accept,
  };
}

/* ── ECA token cache — separate from the PKCE token ── */

let _ecaToken: string | null = null;
let _ecaTokenExpiry = 0;

async function getEcaToken(): Promise<string> {
  if (_ecaToken && Date.now() < _ecaTokenExpiry) return _ecaToken;
  const res = await fetch(`${API_GATEWAY_URL}/oauth/agent-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`ECA token failed: ${res.status}`);
  const data = await res.json();
  _ecaToken = data.access_token;
  _ecaTokenExpiry = Date.now() + 7000 * 1000; // ~2hr minus buffer
  return _ecaToken!;
}

/**
 * Try the real Agent API first. If it 404s, fall back to Apex actions.
 * Returns the sessionId (real or synthetic).
 */
export async function startSession(
  accessToken: string,
  instanceUrl: string,
  agentId: string,
): Promise<string> {
  // Try Agent API first
  try {
    const sessionId = await startAgentApiSession(accessToken, instanceUrl, agentId);
    return sessionId;
  } catch {
    // Agent API not available — use Apex fallback
    console.info('[AgentAPI] Agent API unavailable, using Apex action fallback');
    return startApexFallbackSession();
  }
}

async function startAgentApiSession(
  _accessToken: string, // kept for signature compat but NOT used for Agent API
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

/** Synthetic session for Apex fallback mode */
function startApexFallbackSession(): string {
  return `apex-fallback-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/* ── Apex Action routing ── */

/** Map user intent keywords to Apex invocable actions */
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
  // Default: company lookup
  return { action: 'IR_CompanyLookupAction', inputKey: 'companyName', outputKey: 'companyInfo' };
}

/** Extract a company name/ticker from the user message */
function extractCompanyTerm(text: string): string {
  const cleaned = text
    .replace(/^(show me|look up|get|find|search|tell me about|tell more about|tell us about|what is|what's|what about|describe|explain|give me|info on|details on|details about|more about|about)\s+/i, '')
    .replace(/\s+(company|info|data|details|coverage|filings|earnings|news|sentiment|analysis|financials|10-k|10-q|sec)\b.*/i, '')
    .trim();

  // If the cleaned result still looks like a sentence (has spaces and lowercase),
  // try to extract a ticker-like token instead
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

/** Common words to skip when extracting a ticker symbol */
function isCommonWord(word: string): boolean {
  const common = new Set([
    'THE', 'AND', 'FOR', 'CAN', 'SHOW', 'TELL', 'WHAT', 'WHO', 'WHEN', 'HOW',
    'GET', 'FIND', 'ME', 'MY', 'IS', 'ON', 'IN', 'AT', 'TO', 'OF', 'ABOUT',
    'DOES', 'TRADE', 'LATEST', 'MORE', 'GIVE', 'ALL', 'YOU', 'YOUR', 'SOME',
    'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'HAS', 'NOT', 'BUT', 'ARE', 'WAS',
  ]);
  return common.has(word);
}

/**
 * Derive the correct input value based on the action's inputKey.
 * - `query`: pass the full user message (Apex actions parse it themselves)
 * - `ticker`: extract a ticker-like token (1-5 uppercase letters)
 * - `companyName`: extract the company term from the message
 */
function getInputValue(text: string, inputKey: string): string {
  if (inputKey === 'query') {
    return text;
  }
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
  // companyName
  return extractCompanyTerm(text);
}

/** Call an Apex invocable action via REST API */
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

/** Send a synchronous message (unused in streaming mode, kept for compat) */
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
  _accessToken: string, // kept for signature compat — Agent API uses ECA token
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

/**
 * Send a message with streaming simulation.
 * For Agent API: uses real SSE streaming with ECA token.
 * For Apex fallback: calls the action with PKCE token and simulates streaming.
 */
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
  _accessToken: string, // kept for signature compat — Agent API uses ECA token
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

  /**
   * Salesforce Agent API SSE protocol:
   *   event: TEXT_CHUNK
   *   id: ...
   *   data: {"timestamp":..,"message":{"type":"TextChunk","offset":N,"message":"word "},...}
   *
   *   event: INFORM              ← full final message; emit only if no TEXT_CHUNKs streamed
   *   data: {"message":{"type":"Inform","message":"<complete text>",...}}
   *
   *   event: END_OF_TURN         ← terminates stream
   *
   * Events are delimited by blank lines. We buffer partial chunks across reads.
   */
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on SSE event boundary (blank line)
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() ?? ''; // keep last (possibly incomplete) event in buffer

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
        // non-JSON payload, ignore
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
        // If streaming chunks didn't arrive (non-streaming agent response),
        // emit the full Inform message once so the user sees the reply.
        if (!sawTextChunk && text) {
          fullText = text;
          onChunk(text);
        }
      }
      // PROGRESS_INDICATOR, ROUTE_INFO, etc. — ignored for display
    }
  }
  onComplete?.(fullText);
}

/** Simulate streaming by chunking the Apex response word-by-word */
async function sendApexFallbackStreaming(
  accessToken: string,
  instanceUrl: string,
  message: string,
  onChunk: (text: string) => void,
  onComplete?: (fullText: string) => void,
): Promise<void> {
  const fullText = await sendApexFallbackMessage(accessToken, instanceUrl, message);

  // Simulate streaming: emit words in small batches
  const words = fullText.split(/(\s+)/);
  const BATCH = 3;
  for (let i = 0; i < words.length; i += BATCH) {
    const batch = words.slice(i, i + BATCH).join('');
    onChunk(batch);
    await new Promise((r) => setTimeout(r, 15));
  }
  onComplete?.(fullText);
}

/** End an agent session. Uses ECA token for Agent API, no-op for Apex fallback. */
export async function endSession(
  _accessToken: string,
  _instanceUrl: string,
  sessionId: string,
): Promise<void> {
  if (sessionId.startsWith('apex-fallback-')) {
    return;
  }
  const ecaToken = await getEcaToken();
  const res = await fetch(`${AGENT_API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: headers(ecaToken),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to end session: ${res.status} — ${err}`);
  }
}

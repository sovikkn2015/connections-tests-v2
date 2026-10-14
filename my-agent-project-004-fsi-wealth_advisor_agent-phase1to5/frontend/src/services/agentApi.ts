/**
 * Salesforce Agent API client with Apex Invocable Action fallback.
 *
 * The Agent API (api.salesforce.com/einstein/ai-agent/v1) requires Agentforce
 * to be enabled on the org. When it's not available, we fall back to calling
 * the DC_ Apex InvocableActions directly via the standard REST API.
 *
 * Fallback endpoint: /services/data/v66.0/actions/custom/apex/{ActionName}
 *
 * Agent API calls use an ECA (External Client App) token with chatbot_api scope,
 * fetched via client_credentials grant through the API Gateway proxy.
 * Apex fallback calls continue to use the PKCE access token.
 */

const API_VERSION = 'v66.0';

/* ── Agent API (api.salesforce.com) ── */

const AGENT_API_BASE = 'https://api.salesforce.com/einstein/ai-agent/v1';
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || '';

/* ── ECA Token Cache ── */

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
  _ecaTokenExpiry = Date.now() + 7000 * 1000;
  return _ecaToken!;
}

function headers(accessToken: string, accept = 'application/json'): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    Accept: accept,
  };
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

  if (lower.includes('portfolio') || lower.includes('allocation') || lower.includes('performance') || lower.includes('return')) {
    return { action: 'DC_PortfolioReviewAction', inputKey: 'clientName', outputKey: 'portfolioSummary' };
  }
  if (lower.includes('goal') || lower.includes('retirement') || lower.includes('college') || lower.includes('target') || lower.includes('saving')) {
    return { action: 'DC_GoalPlanningAction', inputKey: 'clientName', outputKey: 'goalsSummary' };
  }
  if (lower.includes('meeting') || lower.includes('prep') || lower.includes('prepare') || lower.includes('agenda')) {
    return { action: 'DC_MeetingPrepAction', inputKey: 'clientName', outputKey: 'meetingBrief' };
  }
  if (lower.includes('rebalance') || lower.includes('rebalancing') || lower.includes('drift') || lower.includes('allocation check')) {
    return { action: 'DC_RebalancingAction', inputKey: 'clientName', outputKey: 'rebalancingAnalysis' };
  }
  if (lower.includes('transaction') || lower.includes('trade') || lower.includes('buy') || lower.includes('sell') || lower.includes('dividend')) {
    return { action: 'DC_TransactionHistoryAction', inputKey: 'clientName', outputKey: 'transactionHistory' };
  }
  if (lower.includes('compliance') || lower.includes('suitability') || lower.includes('risk check') || lower.includes('concentration')) {
    return { action: 'DC_ComplianceCheckAction', inputKey: 'clientName', outputKey: 'complianceReport' };
  }
  if (lower.includes('referral') || lower.includes('referred') || lower.includes('who referred')) {
    return { action: 'DC_ReferralTrackingAction', inputKey: 'clientName', outputKey: 'referralInfo' };
  }
  if (lower.includes('market') || lower.includes('stock') || lower.includes('index') || lower.includes('sector') || lower.includes('quote')) {
    return { action: 'DC_MarketDataAction', inputKey: 'query', outputKey: 'marketSummary' };
  }
  if (lower.includes('news') || lower.includes('headline')) {
    return { action: 'DC_NewsSearchAction', inputKey: 'query', outputKey: 'newsSummary' };
  }
  // Default: client lookup
  return { action: 'DC_ClientLookupAction', inputKey: 'clientName', outputKey: 'clientSummary' };
}

/** Extract a client name from the user message */
function extractClientName(text: string): string {
  const cleaned = text
    .replace(/^(show me|look up|get|find|search|tell me about|tell more about|what about|describe|give me|info on|details on|details about|more about|about|how is|how are|what are|prep me for|prepare for)\s+/i, '')
    .replace(/\s+(household|family|portfolio|goals|meeting|transactions|compliance|referral|account|client|info|data|details|history|check|alert|recent|prep|rebalancing|needs)\b.*/i, '')
    .replace(/\b(the|my|a|an)\s+/gi, '')
    .replace(/'s\b/gi, '')
    .trim();
  return cleaned || text.trim();
}

/**
 * Derive the correct input value based on the action's inputKey.
 * - `query`: pass the full user message (Apex actions parse it themselves)
 * - `clientName`: extract the client name from the message
 */
function getInputValue(text: string, inputKey: string): string {
  if (inputKey === 'query') {
    return text;
  }
  // clientName (default)
  return extractClientName(text);
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

/**
 * Send a message with streaming simulation.
 * For Agent API: uses real SSE streaming.
 * For Apex fallback: calls the action and simulates streaming by chunking the response.
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

  /**
   * Salesforce Agent API SSE protocol:
   *   event: TEXT_CHUNK
   *   data: {"message":{"type":"TextChunk","message":"word ",...}}
   *   event: INFORM          ← full final message (emit only if no chunks streamed)
   *   event: END_OF_TURN     ← terminates stream
   * Events are delimited by blank lines.
   */
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

/** End an agent session. */
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

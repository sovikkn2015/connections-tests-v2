/**
 * AgentCore HTTP → OpenClaw REST adapter.
 *
 * AgentCore sends HTTP on :8080 (POST /invocations, GET /ping).
 * OpenClaw Gateway exposes REST on :18789.
 * This adapter bridges the two — pure HTTP, no WebSocket.
 *
 * Strategy:
 *   PRIMARY:  POST /v1/chat/completions (OpenAI-compatible, synchronous with stream:false)
 *   FALLBACK: POST /hooks/agent (async hook invocation)
 *
 * Both require Authorization: Bearer <token> matching the gateway's configured auth token.
 *
 * Protocol flow:
 *   AgentCore → POST /invocations { prompt, sessionKey }
 *   Adapter   → POST http://gateway:18789/v1/chat/completions
 *   Gateway   → { choices: [{ message: { content } }] }
 *   Adapter   → HTTP 200 { response }  back to AgentCore
 */

import express from 'express';

/* ── Config (all from env — zero hardcoded credentials) ── */
const PORT = parseInt(process.env.ADAPTER_PORT || '8080', 10);
const GATEWAY_HOST = process.env.GATEWAY_HOST || 'localhost';
const GATEWAY_PORT = parseInt(process.env.GATEWAY_PORT || '18789', 10);
const GATEWAY_TOKEN = process.env.OPENCLAW_GATEWAY_TOKEN || '';
const HOOKS_TOKEN = process.env.OPENCLAW_HOOKS_TOKEN || '';
const GATEWAY_BASE = `http://${GATEWAY_HOST}:${GATEWAY_PORT}`;
const REQUEST_TIMEOUT_MS = 600_000; // 600s — matches OpenClaw agent timeout

/* ── Logging ── */
function log(level, msg, data) {
  const entry = { ts: new Date().toISOString(), level, msg, ...data };
  console[level === 'error' ? 'error' : 'log'](JSON.stringify(entry));
}

/* ── Auth headers (always include token) ── */
function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (GATEWAY_TOKEN) {
    headers['Authorization'] = `Bearer ${GATEWAY_TOKEN}`;
  }
  return headers;
}

/* ── Gateway health check ── */
async function isGatewayHealthy() {
  try {
    const res = await fetch(`${GATEWAY_BASE}/health`, {
      signal: AbortSignal.timeout(5_000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/* ── PRIMARY: OpenAI-compatible chat completions (synchronous) ── */
async function sendViaChatCompletions(message, sessionKey, agentId) {
  const url = `${GATEWAY_BASE}/v1/chat/completions`;

  log('info', 'sending via /v1/chat/completions', { sessionKey, agentId });

  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      model: agentId ? `openclaw/${agentId}` : 'openclaw',
      messages: [{ role: 'user', content: message }],
      stream: false,
      user: sessionKey,
    }),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    log('warn', 'chat completions failed', { status: res.status, body: body.slice(0, 500) });
    throw new Error(`Chat completions returned ${res.status}: ${body}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content || JSON.stringify(data);
}

/* ── FALLBACK: Hooks agent endpoint (synchronous via waitForResponse) ── */
async function sendViaHooksAgent(message, sessionKey, agentId) {
  const url = `${GATEWAY_BASE}/hooks/agent`;

  log('info', 'sending via /hooks/agent (sync)', { sessionKey, agentId });

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(HOOKS_TOKEN ? { 'Authorization': `Bearer ${HOOKS_TOKEN}` } : {}),
    },
    body: JSON.stringify({
      message,
      agentId: agentId || 'fsi-research',
      sessionKey,
      deliver: false,
      thinking: 'medium',
      waitForResponse: true,
      timeoutSeconds: Math.floor(REQUEST_TIMEOUT_MS / 1000),
    }),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Hooks agent returned ${res.status}: ${body}`);
  }

  const data = await res.json();
  if (data.response) return data.response;
  if (data.text) return data.text;
  if (data.result?.text) return data.result.text;
  if (data.result?.response) return data.result.response;
  // If still async, return what we have
  return JSON.stringify(data);
}

/* ── Express server (AgentCore contract: GET /ping, POST /invocations) ── */

const app = express();
app.use(express.json({ limit: '1mb' }));

app.get('/ping', async (_req, res) => {
  const gatewayUp = await isGatewayHealthy();
  res.json({ status: gatewayUp ? 'healthy' : 'degraded', gateway: gatewayUp });
});

app.post('/invocations', async (req, res) => {
  const { prompt, sessionKey, action, userId, actorId, agentId } = req.body || {};
  const message = prompt || req.body?.message || '';
  const session = sessionKey || userId || 'default';
  const agent = agentId || 'fsi-research';

  if (!message) {
    return res.status(400).json({ error: 'Missing prompt' });
  }

  // Strategy: /v1/chat/completions first (synchronous), then /hooks/agent fallback
  const strategies = [
    { name: 'chat-completions', fn: () => sendViaChatCompletions(message, session, agent) },
    { name: 'chat-completions-retry', fn: async () => {
      // Wait 2s for gateway to stabilize after a restart, then retry
      await new Promise(r => setTimeout(r, 2000));
      return sendViaChatCompletions(message, session, agent);
    }},
    { name: 'hooks-agent', fn: () => sendViaHooksAgent(message, session, agent) },
  ];

  for (const { name, fn } of strategies) {
    try {
      const response = await fn();
      log('info', 'invocation succeeded', { strategy: name, session });
      return res.json({ response, strategy: name });
    } catch (err) {
      log('warn', `strategy ${name} failed`, { error: err.message });
    }
  }

  log('error', 'all strategies failed', { session });
  res.status(502).json({ error: 'All gateway strategies failed' });
});

/* ── Startup ── */

async function start() {
  // Wait for gateway to be reachable (start.sh launches it first)
  const maxWait = 60;
  for (let i = 0; i < maxWait; i++) {
    if (await isGatewayHealthy()) {
      log('info', 'gateway is healthy');
      break;
    }
    if (i === maxWait - 1) {
      log('warn', 'gateway not healthy after timeout, starting adapter anyway');
    }
    await new Promise(r => setTimeout(r, 1_000));
  }

  app.listen(PORT, '0.0.0.0', () => {
    log('info', `adapter listening on :${PORT}`, { gateway: GATEWAY_BASE });
  });
}

start();

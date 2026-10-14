/**
 * OpenClaw Gateway client — WebSocket (local dev) or REST proxy (production).
 * Replaces Salesforce Agent API from 005 V2.
 *
 * Modes:
 * - REST (production): POST to AGENT_PROXY_URL → Lambda → AgentCore → OpenClaw
 *   Used when VITE_AGENT_PROXY_URL is set. No WebSocket needed.
 * - WebSocket (local dev): JSON-RPC 2.0 over WebSocket to OpenClaw Gateway
 *   Used when VITE_AGENT_PROXY_URL is not set.
 *
 * Features:
 * - Automatic mode selection based on VITE_AGENT_PROXY_URL
 * - Exponential backoff reconnection for WebSocket mode (1s → 30s max)
 * - Connection state callback for UI sync
 * - Pending request cleanup on disconnect
 * - Heartbeat ping every 30s (WebSocket mode only)
 * - Proper cleanup on disconnect/destroy
 */

const GATEWAY_URL = import.meta.env.VITE_OPENCLAW_GATEWAY_URL || 'ws://localhost:18789';
const AGENT_PROXY_URL = import.meta.env.VITE_AGENT_PROXY_URL || '';
const AGENTCORE_AUTH_MODE = import.meta.env.VITE_AGENTCORE_AUTH_MODE || ''; // 'oauth' for AgentCore

/** True when the REST proxy is configured (production CloudFront deployment) */
function useRestMode(): boolean {
  return !!AGENT_PROXY_URL;
}

/**
 * SF OAuth token — set by the auth layer after SF OAuth PKCE completes.
 * Used for both AgentCore WebSocket auth (Sec-WebSocket-Protocol header)
 * and the connect RPC auth payload. No static gateway token in the bundle.
 */
let sfAuthToken = '';

/** Set the SF OAuth token for OpenClaw authentication */
export function setAuthToken(token: string): void {
  sfAuthToken = token;
}

/**
 * @deprecated Use setAuthToken instead. Kept for backward compatibility.
 */
export function setOAuthToken(token: string): void {
  setAuthToken(token);
}

/* ── Reconnection constants ── */
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
const BACKOFF_MULTIPLIER = 2;
const HEARTBEAT_INTERVAL_MS = 30000;
const REQUEST_TIMEOUT_MS = 120000;

/* ── Module state ── */
let ws: WebSocket | null = null;
let requestId = 0;
let connected = false;
let intentionalClose = false;

/* Reconnection state */
let currentBackoff = INITIAL_BACKOFF_MS;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

/* Heartbeat state */
let heartbeatInterval: ReturnType<typeof setInterval> | null = null;

/* Pending RPC requests */
const pendingRequests = new Map<number, {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
}>();

/* Stream callback */
let streamCallback: StreamCallback | null = null;

/* Connection state observer */
let onConnectionChange: ((connected: boolean) => void) | null = null;

/* MuleSoft HITL observer — fires for canonical `hitl.pending` / `hitl.completed`
 * envelopes emitted by the OpenClaw Gateway when a MuleSoft write action
 * requires human approval. Kept separate from StreamCallback so gates
 * survive beyond the lifetime of a single agent run. */
let onHitlPending:
  | ((event: import('../types').HitlPendingEvent) => void)
  | null = null;
let onHitlCompleted:
  | ((event: import('../types').HitlCompletedEvent) => void)
  | null = null;

export interface StreamCallback {
  onText: (chunk: string) => void;
  onToolStart: (name: string, toolCallId: string, input: unknown) => void;
  onToolResult: (name: string, toolCallId: string, result: unknown) => void;
  onToolError: (name: string, toolCallId: string, error: string) => void;
  onLifecycle: (phase: 'start' | 'thinking' | 'end' | 'error') => void;
  onComplete: (fullText: string) => void;
}

/** Register a callback that fires whenever connection state changes */
export function setConnectionChangeCallback(cb: (connected: boolean) => void): void {
  onConnectionChange = cb;
}

/** Register a callback that fires when a MuleSoft `hitl.pending` event arrives. */
export function setHitlPendingCallback(
  cb: (event: import('../types').HitlPendingEvent) => void,
): void {
  onHitlPending = cb;
}

/** Register a callback that fires when a MuleSoft `hitl.completed` event arrives. */
export function setHitlCompletedCallback(
  cb: (event: import('../types').HitlCompletedEvent) => void,
): void {
  onHitlCompleted = cb;
}

function setConnected(value: boolean): void {
  connected = value;
  onConnectionChange?.(value);
}

function nextId(): number {
  return ++requestId;
}

/** Reject and clean up ALL pending requests (called on disconnect) */
function rejectAllPending(reason: string): void {
  for (const [id, entry] of pendingRequests) {
    clearTimeout(entry.timer);
    entry.reject(new Error(reason));
    pendingRequests.delete(id);
  }
}

/** Clear stream callback to prevent stale callbacks after disconnect */
function clearStreamCallback(): void {
  streamCallback = null;
}

/** Start heartbeat ping to keep connection alive through proxies/LBs */
function startHeartbeat(): void {
  stopHeartbeat();
  heartbeatInterval = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ jsonrpc: '2.0', method: 'ping', params: {} }));
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat(): void {
  if (heartbeatInterval !== null) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

/** Clear reconnect timer */
function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

/** Schedule a reconnection attempt with exponential backoff */
function scheduleReconnect(): void {
  if (intentionalClose) return;
  clearReconnectTimer();

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectInternal().catch(() => {
      // connectInternal handles its own error → scheduleReconnect cycle
    });
  }, currentBackoff);

  // Increase backoff for next attempt (capped at MAX_BACKOFF_MS)
  currentBackoff = Math.min(currentBackoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_MS);
}

/** Reset backoff to initial value (called on successful connect) */
function resetBackoff(): void {
  currentBackoff = INITIAL_BACKOFF_MS;
}

function sendRpc(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      reject(new Error('WebSocket not connected'));
      return;
    }
    const id = nextId();
    const timer = setTimeout(() => {
      if (pendingRequests.has(id)) {
        pendingRequests.delete(id);
        reject(new Error(`Request ${method} timed out`));
      }
    }, REQUEST_TIMEOUT_MS);

    pendingRequests.set(id, { resolve, reject, timer });
    ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }));
  });
}

/**
 * Canonical MuleSoft HITL event router.
 *
 * Backend emits three wire types over the agent stream:
 *   - { type: "hitl.pending",   token_hash, plan_hash, action, summary_text, ... }
 *   - { type: "hitl.completed", token_hash, plan_hash, decision, mulesoft_reference?, ... }
 * Decisions go OUT via `sendHitlDecision`:
 *   - { type: "hitl.decision",  token_hash, decision, approver_note? }
 *
 * Rule 21: summary_text + plan_details are for humans — never logged,
 * never re-prompted. Rule 22: raw approval tokens never enter the
 * browser; only token_hash (sha256 prefix, 16 chars) does.
 */
function handleHitlEvent(data: Record<string, unknown>): void {
  const t = data.type;

  if (t === 'hitl.pending') {
    if (!onHitlPending) return;
    // Minimal shape validation; the full contract is documented in types/index.ts
    if (typeof data.token_hash !== 'string' || typeof data.plan_hash !== 'string') {
      console.warn('[openclawApi] hitl.pending missing token_hash / plan_hash');
      return;
    }
    onHitlPending(data as unknown as import('../types').HitlPendingEvent);
    return;
  }

  if (t === 'hitl.completed') {
    if (!onHitlCompleted) return;
    if (typeof data.token_hash !== 'string' || typeof data.decision !== 'string') {
      console.warn('[openclawApi] hitl.completed missing token_hash / decision');
      return;
    }
    onHitlCompleted(data as unknown as import('../types').HitlCompletedEvent);
    return;
  }
}

function handleMessage(event: MessageEvent): void {
  try {
    const frame = JSON.parse(event.data);

    // RPC response
    if (frame.id && pendingRequests.has(frame.id)) {
      const { resolve: res, reject: rej, timer } = pendingRequests.get(frame.id)!;
      clearTimeout(timer);
      pendingRequests.delete(frame.id);
      if (frame.ok) {
        res(frame.payload);
      } else {
        rej(new Error(frame.error?.message || 'Unknown error'));
      }
      return;
    }

    // Streaming event
    if (frame.event === 'agent' && streamCallback) {
      const { stream, data } = frame.payload || {};

      if (stream === 'assistant' && data?.text) {
        streamCallback.onText(data.text);
      } else if (stream === 'tool') {
        if (data?.phase === 'start') {
          streamCallback.onToolStart(data.name, data.toolCallId, data.input);
        } else if (data?.phase === 'result') {
          streamCallback.onToolResult(data.name, data.toolCallId, data.result);
        } else if (data?.phase === 'error') {
          streamCallback.onToolError(data.name, data.toolCallId, data.error);
        }
      } else if (stream === 'lifecycle') {
        streamCallback.onLifecycle(data?.phase || 'end');
        if (data?.phase === 'end') {
          streamCallback.onComplete('');
        }
      }
    }

    // HITL events — the OpenClaw Gateway can emit them in three shapes:
    //   1. Top-level envelope:   { "type": "hitl.pending", ... }
    //   2. stream='hitl' inside an `event=agent` frame (legacy)
    //   3. `event=hitl` wrapper: { "event": "hitl", "payload": {...} }
    // The canonical contract (docs/v2-end-to-end-wiring-assessment.md) is #1.
    if (frame && typeof frame === 'object') {
      if (
        frame.type === 'hitl.pending' ||
        frame.type === 'hitl.completed'
      ) {
        handleHitlEvent(frame as Record<string, unknown>);
        return;
      }
      if (frame.event === 'hitl' && frame.payload && typeof frame.payload === 'object') {
        handleHitlEvent(frame.payload as Record<string, unknown>);
        return;
      }
      if (frame.event === 'agent' && frame.payload) {
        const { stream, data } = frame.payload;
        if (stream === 'hitl' && data && typeof data === 'object') {
          handleHitlEvent(data as Record<string, unknown>);
        }
      }
    }
  } catch {
    // Ignore parse errors on non-JSON frames
  }
}

/** Internal connect — used by both initial connect() and reconnection */
function connectInternal(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      resolve();
      return;
    }

    // Clean up any existing socket in non-OPEN state
    if (ws) {
      try { ws.close(); } catch { /* ignore */ }
      ws = null;
    }

    // AgentCore auth: encode OAuth token in Sec-WebSocket-Protocol header.
    // AgentCore's /ws endpoint proxies raw WebSocket frames to the container's
    // /ws handler, which bridges to OpenClaw Gateway on port 18789.
    // The frontend speaks OpenClaw's JSON-RPC protocol end-to-end.
    if (AGENTCORE_AUTH_MODE === 'oauth' && sfAuthToken) {
      const base64url = btoa(sfAuthToken)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');
      ws = new WebSocket(GATEWAY_URL, [
        `base64UrlBearerAuthorization.${base64url}`,
        'base64UrlBearerAuthorization',
      ]);
    } else {
      ws = new WebSocket(GATEWAY_URL);
    }

    ws.onopen = async () => {
      try {
        await sendRpc('connect', {
          role: 'control',
          auth: { mode: 'oauth', token: sfAuthToken },
          client: { name: '006-FSI-Workbench', version: '1.0.0' },
        });
        setConnected(true);
        resetBackoff();
        startHeartbeat();
        resolve();
      } catch (err) {
        reject(err);
      }
    };

    ws.onmessage = handleMessage;

    ws.onerror = () => {
      if (!connected) {
        reject(new Error('WebSocket connection failed'));
      }
    };

    ws.onclose = () => {
      stopHeartbeat();
      rejectAllPending('WebSocket disconnected');
      clearStreamCallback();
      setConnected(false);
      ws = null;

      // Auto-reconnect if this wasn't an intentional close
      if (!intentionalClose) {
        scheduleReconnect();
      }
    };
  });
}

/** Connect to OpenClaw Gateway WebSocket.
 *
 * Even in REST mode (production via AGENT_PROXY_URL), we still establish a
 * WebSocket because HITL events are push-only: the backend emits
 * `hitl.pending` / `hitl.completed` asynchronously and the browser must
 * be listening. Agent queries themselves may go over REST (see
 * `sendMessage`), but the event stream has no REST fallback.
 */
export function connect(): Promise<void> {
  intentionalClose = false;
  // No gateway URL configured at all (e.g. unit-test or unconfigured env) —
  // mark "connected" so the REST path works without an error banner.
  if (!GATEWAY_URL) {
    setConnected(true);
    return Promise.resolve();
  }
  return connectInternal().catch((err) => {
    if (useRestMode()) {
      // In REST mode, WS is best-effort: don't fail the whole login.
      // The auto-reconnect loop keeps trying. HITL push events will start
      // flowing as soon as the socket comes up.
      setConnected(true);
      console.warn('[openclawApi] WS event stream unavailable, continuing in REST-only mode:', err);
      return;
    }
    throw err;
  });
}

/** Disconnect from OpenClaw Gateway — full cleanup */
export function disconnect(): void {
  intentionalClose = true;
  clearReconnectTimer();
  stopHeartbeat();
  rejectAllPending('Disconnected by client');
  clearStreamCallback();

  if (ws) {
    try { ws.close(); } catch { /* ignore */ }
    ws = null;
  }

  setConnected(false);
}

/** Check if connected */
export function isConnected(): boolean {
  if (useRestMode()) {
    // In REST mode we are "functional" whenever the REST proxy is configured;
    // WS-only features (HITL push) gracefully degrade if the WS is not up.
    return connected;
  }
  return connected && ws?.readyState === WebSocket.OPEN;
}

/* ── Rate limiting: sliding window (max 5 messages per 10 seconds) ── */
const RATE_LIMIT_WINDOW_MS = 10_000;
const RATE_LIMIT_MAX_MESSAGES = 5;
const messageTimestamps: number[] = [];
let rateLimitedUntil = 0;

/** Check if the client is currently rate limited */
export function isRateLimited(): boolean {
  const now = Date.now();
  if (now < rateLimitedUntil) return true;
  // Prune timestamps outside the window
  while (messageTimestamps.length > 0 && messageTimestamps[0] <= now - RATE_LIMIT_WINDOW_MS) {
    messageTimestamps.shift();
  }
  return messageTimestamps.length >= RATE_LIMIT_MAX_MESSAGES;
}

/** Record a sent message timestamp and enforce the sliding window */
function recordMessage(): boolean {
  const now = Date.now();
  // Prune old timestamps
  while (messageTimestamps.length > 0 && messageTimestamps[0] <= now - RATE_LIMIT_WINDOW_MS) {
    messageTimestamps.shift();
  }
  if (messageTimestamps.length >= RATE_LIMIT_MAX_MESSAGES) {
    // Calculate when the oldest message in the window expires
    rateLimitedUntil = messageTimestamps[0] + RATE_LIMIT_WINDOW_MS;
    return false;
  }
  messageTimestamps.push(now);
  return true;
}

/**
 * Send a message via REST proxy (production mode).
 * POST { message, sessionKey } → Lambda → AgentCore → OpenClaw → JSON response.
 * Simulates streaming callbacks with the full response at once.
 */
async function sendMessageViaRest(
  message: string,
  sessionKey: string,
  callback: StreamCallback,
): Promise<string> {
  const runId = `run-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  callback.onLifecycle('start');

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (sfAuthToken) {
    headers['Authorization'] = `Bearer ${sfAuthToken}`;
  }

  const res = await fetch(AGENT_PROXY_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, sessionKey }),
  });

  if (!res.ok) {
    const errBody = await res.text().catch(() => '');
    callback.onLifecycle('error');
    throw new Error(`Agent proxy returned ${res.status}: ${errBody}`);
  }

  const data = await res.json();
  const responseText = data.response || JSON.stringify(data);

  // Process tool results returned by the agent proxy (if any).
  // These are the same events that WebSocket mode delivers via onToolStart/onToolResult.
  const toolResults = data.toolResults as
    | { name: string; toolCallId: string; phase?: string; result?: unknown; input?: unknown }[]
    | undefined;
  if (Array.isArray(toolResults)) {
    for (const tr of toolResults) {
      if (tr.phase === 'start') {
        callback.onToolStart(tr.name, tr.toolCallId, tr.input);
      } else {
        // Default to result phase
        callback.onToolResult(tr.name, tr.toolCallId, tr.result);
      }
    }
  }

  callback.onText(responseText);
  callback.onLifecycle('end');
  callback.onComplete(responseText);

  return runId;
}

/** Send a message to the agent — routes through REST proxy or WebSocket */
export async function sendMessage(
  message: string,
  sessionKey: string,
  agentId: string = 'fsi-research',
  callback: StreamCallback,
): Promise<string> {
  if (!recordMessage()) {
    throw new Error('Rate limited — max 5 messages per 10 seconds. Please wait.');
  }

  // REST mode: POST to agent proxy Lambda (production)
  if (useRestMode()) {
    return sendMessageViaRest(message, sessionKey, callback);
  }

  // WebSocket mode: JSON-RPC to OpenClaw Gateway (local dev)
  streamCallback = callback;
  const runId = `run-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  await sendRpc('agent', {
    message,
    sessionKey,
    runId,
    agentId,
    thinking: 'medium',
    deliver: false,
  });

  return runId;
}

/** Abort an in-progress agent run */
export async function abortRun(runId: string): Promise<void> {
  await sendRpc('chat.abort', { runId });
}

/**
 * Send an approver decision for a MuleSoft HITL gate.
 *
 * Emits the canonical `hitl.decision` wire message:
 *   { "type": "hitl.decision", "token_hash": "...", "decision": "APPROVED"|"REJECTED", "approver_note": "..." }
 *
 * The backend matches token_hash to an outstanding pending approval,
 * verifies the HMAC, and writes the decision to IR_Audit_Log__c.
 *
 * Rule 22: we MUST NOT log the token_hash in raw form. Only the first
 * 8 hex chars are logged for forensic correlation with the backend.
 */
export async function sendHitlDecision(
  tokenHash: string,
  decision: 'APPROVED' | 'REJECTED',
  approverNote?: string,
): Promise<void> {
  const payload: Record<string, unknown> = {
    type: 'hitl.decision',
    token_hash: tokenHash,
    decision,
  };
  if (approverNote && approverNote.trim()) {
    payload.approver_note = approverNote.trim().slice(0, 500);
  }

  // REST mode: the AgentCore proxy Lambda bridges the decision back to
  // the gateway on a dedicated route. WebSocket mode ships it directly.
  if (useRestMode()) {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (sfAuthToken) headers['Authorization'] = `Bearer ${sfAuthToken}`;
    const url = AGENT_PROXY_URL.replace(/\/agent\/query\/?$/, '/hitl/decision');
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`HITL decision POST failed (${res.status}): ${body}`);
    }
    return;
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    throw new Error('WebSocket not connected — cannot send HITL decision');
  }
  ws.send(JSON.stringify(payload));
}

/** Get agent identity/metadata */
export async function getAgentIdentity(agentId: string = 'fsi-research'): Promise<unknown> {
  return sendRpc('agent.identity.get', { agentId });
}

/** List all configured agents */
export async function listAgents(): Promise<unknown> {
  return sendRpc('agents.list', {});
}

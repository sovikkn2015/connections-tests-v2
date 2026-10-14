/**
 * Unit tests for agentApi.ts — V3 headers + gateway fallback behaviour.
 * All network calls are intercepted by MSW; no live calls occur.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../test/msw-server';
import {
  __internal,
  getGatewayBaseUrl,
  isFlexGatewayActive,
  startSession,
  endSession,
} from './agentApi';

describe('agentApi V3 headers', () => {
  beforeEach(() => {
    sessionStorage.clear();
    __internal.clearCorrelationId();
  });

  it('adds X-Correlation-Id and X-Agent-Id to the Agent API session request', async () => {
    let captured: Headers | null = null;

    server.use(
      http.post('https://api.example.test/oauth/agent-token', () =>
        HttpResponse.json({ access_token: 'eca-token-abc' }),
      ),
      http.post(
        'https://api.salesforce.com/einstein/ai-agent/v1/agents/:agentId/sessions',
        ({ request }) => {
          captured = request.headers;
          return HttpResponse.json({ sessionId: 'sess-123' });
        },
      ),
    );

    const sid = await startSession('pkce-token', 'https://inst.salesforce.com', 'test-agent');
    expect(sid).toBe('sess-123');
    expect(captured).not.toBeNull();
    const corr = captured!.get('x-correlation-id');
    expect(corr).toBeTruthy();
    expect(corr!.length).toBeGreaterThanOrEqual(8);
    expect(captured!.get('x-agent-id')).toBe('ir-research-orchestrator');
    expect(captured!.get('authorization')).toBe('Bearer eca-token-abc');
  });

  it('keeps the same correlation ID across follow-up calls within a session', async () => {
    const seen: string[] = [];
    server.use(
      http.post('https://api.example.test/oauth/agent-token', ({ request }) => {
        seen.push(request.headers.get('x-correlation-id') ?? '');
        return HttpResponse.json({ access_token: 't' });
      }),
      http.post(
        'https://api.salesforce.com/einstein/ai-agent/v1/agents/:agentId/sessions',
        ({ request }) => {
          seen.push(request.headers.get('x-correlation-id') ?? '');
          return HttpResponse.json({ sessionId: 'sess-1' });
        },
      ),
      http.delete('https://api.salesforce.com/einstein/ai-agent/v1/sessions/:sid', ({ request }) => {
        seen.push(request.headers.get('x-correlation-id') ?? '');
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await startSession('pkce', 'https://inst', 'a');
    await endSession('pkce', 'https://inst', 'sess-1');
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen[0]).toBe(seen[1]);
  });

  it('rotates the correlation ID on a brand-new session', async () => {
    server.use(
      http.post('https://api.example.test/oauth/agent-token', () =>
        HttpResponse.json({ access_token: 't' }),
      ),
      http.post(
        'https://api.salesforce.com/einstein/ai-agent/v1/agents/:agentId/sessions',
        () => HttpResponse.json({ sessionId: 'sess-x' }),
      ),
    );

    await startSession('pkce', 'https://inst', 'a');
    const first = __internal.getCorrelationId();
    await startSession('pkce', 'https://inst', 'a');
    const second = __internal.getCorrelationId();
    expect(second).not.toBe(first);
  });

  it('falls back to an apex-fallback session when Agent API fails', async () => {
    server.use(
      http.post('https://api.example.test/oauth/agent-token', () =>
        HttpResponse.json({ access_token: 't' }),
      ),
      http.post(
        'https://api.salesforce.com/einstein/ai-agent/v1/agents/:agentId/sessions',
        () => new HttpResponse('nope', { status: 500 }),
      ),
    );
    const sid = await startSession('pkce', 'https://inst', 'a');
    expect(sid.startsWith('apex-fallback-')).toBe(true);
  });
});

describe('getGatewayBaseUrl / isFlexGatewayActive', () => {
  it('defaults to API Gateway when VITE_FLEX_GATEWAY_URL is unset (V2 fallback)', () => {
    expect(getGatewayBaseUrl()).toBe('https://api.example.test');
    expect(isFlexGatewayActive()).toBe(false);
  });
});

/**
 * Unit tests for visualizerApi.ts — primary/fallback/stub resolution.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../test/msw-server';
import { fetchSnapshot, emptySnapshot } from './visualizerApi';
import { __internal } from './agentApi';

describe('fetchSnapshot', () => {
  beforeEach(() => {
    sessionStorage.clear();
    __internal.clearCorrelationId();
  });

  it('returns an Anypoint snapshot when the API responds', async () => {
    server.use(
      http.get('https://anypoint.example/api/traces/:cid', ({ params }) =>
        HttpResponse.json({
          correlationId: params.cid,
          observedAt: '2025-01-01T00:00:00Z',
          nodes: [{ id: 'user', kind: 'user', label: 'Analyst' }],
          edges: [],
          events: [
            {
              id: 'e1',
              timestamp: '2025-01-01T00:00:00Z',
              correlationId: params.cid as string,
              agentId: 'ir-research-orchestrator',
              kind: 'mcp.call.start',
              message: 'get_10k',
              latencyMs: 120,
            },
          ],
        }),
      ),
    );

    const snap = await fetchSnapshot('cid-123');
    expect(snap.source).toBe('anypoint');
    expect(snap.graph.correlationId).toBe('cid-123');
    expect(snap.events).toHaveLength(1);
    expect(snap.events[0].kind).toBe('mcp.call.start');
  });

  it('falls back to Langfuse when Anypoint fails', async () => {
    server.use(
      http.get('https://anypoint.example/api/traces/:cid', () =>
        new HttpResponse(null, { status: 503 }),
      ),
      http.get('https://langfuse.example/api/public/traces', () =>
        HttpResponse.json({
          data: [
            {
              id: 'tr-1',
              name: 'research',
              timestamp: '2025-01-01T00:00:00Z',
              observations: [
                {
                  id: 'obs-1',
                  type: 'span',
                  name: 'mcp-call:get_10k',
                  startTime: '2025-01-01T00:00:00.000Z',
                  endTime: '2025-01-01T00:00:00.500Z',
                },
              ],
            },
          ],
        }),
      ),
    );

    const snap = await fetchSnapshot('cid-lf');
    expect(snap.source).toBe('langfuse');
    expect(snap.events).toHaveLength(1);
    expect(snap.events[0].latencyMs).toBe(500);
    const mcpNode = snap.graph.nodes.find((n) => n.kind === 'mcp');
    expect(mcpNode?.detail).toBe('mcp-call:get_10k');
  });

  it('returns a stub snapshot when both providers fail', async () => {
    server.use(
      http.get('https://anypoint.example/api/traces/:cid', () => new HttpResponse(null, { status: 500 })),
      http.get('https://langfuse.example/api/public/traces', () => new HttpResponse(null, { status: 500 })),
    );
    const snap = await fetchSnapshot('cid-stub');
    expect(snap.source).toBe('stub');
    expect(snap.graph.correlationId).toBe('cid-stub');
    expect(snap.events).toEqual([]);
  });

  it('emptySnapshot has the expected 6-node chain', () => {
    const s = emptySnapshot();
    expect(s.graph.nodes.map((n) => n.kind)).toEqual([
      'user',
      'agent',
      'gateway',
      'mcp',
      'data',
      'response',
    ]);
  });
});

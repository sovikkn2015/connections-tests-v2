/**
 * Per-test REST stub — fetch replacement for RestClient. Replaces MSW after
 * MSW's WebSocket interceptor proved incompatible with our MockWebSocket.
 */

import type { SourceChunk, SourceTable } from '../../src/shared/types/api';

const TABLE: SourceTable = {
  source_id: 'stub',
  title: 'NVDA Revenue Mix — FY25',
  columns: ['FY23', 'FY24', 'FY25'],
  rows: [
    { key: 'datacenter', label: 'Data Center', values: { FY23: 15005, FY24: 47525, FY25: 115186 } },
    { key: 'gaming', label: 'Gaming', values: { FY23: 9067, FY24: 10447, FY25: 11350 } },
  ],
  as_of: '2025-02-26',
  citation: {
    span_id: 'span-42',
    source_id: 'stub',
    source_type: 'filing',
    label: 'NVDA 10-K FY25 Item 7',
    page: 42,
  },
};

const CHUNK: SourceChunk = {
  source_id: 'stub',
  title: 'NVDA 10-K FY25 — Item 1A Risk Factors',
  filing_type: '10-K',
  filing_date: '2025-02-21',
  section: 'Item 1A',
  page: 12,
  text: 'Our success depends on continued demand for our GPU products.',
};

export function createStubFetch(): typeof fetch {
  return (async (input: RequestInfo | URL): Promise<Response> => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : (input as Request).url ?? String(input);
    if (url.includes('/api/source_tables/')) {
      const id = url.split('/api/source_tables/')[1]!.split('?')[0]!;
      return new Response(JSON.stringify({ ...TABLE, source_id: id }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url.includes('/api/source_chunk/')) {
      const id = url.split('/api/source_chunk/')[1]!.split('?')[0]!;
      return new Response(JSON.stringify({ ...CHUNK, source_id: id }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url.includes('/api/session/warm')) {
      return new Response(null, { status: 204 });
    }
    return new Response('Not Found', { status: 404 });
  }) as unknown as typeof fetch;
}

/**
 * MSW handlers — REST stubs for source_tables / source_chunk / session/warm.
 * Tests can override per-test with server.use().
 */

import { http, HttpResponse } from 'msw';
import type { SourceChunk, SourceTable } from '../../src/shared/types/api';

const TABLE: SourceTable = {
  source_id: 'nvda_revenue_fy25',
  title: 'NVDA Revenue Mix — FY25',
  columns: ['FY23', 'FY24', 'FY25'],
  rows: [
    { key: 'datacenter', label: 'Data Center', values: { FY23: 15005, FY24: 47525, FY25: 115186 } },
    { key: 'gaming', label: 'Gaming', values: { FY23: 9067, FY24: 10447, FY25: 11350 } },
    { key: 'pro_viz', label: 'Pro Viz', values: { FY23: 1544, FY24: 1553, FY25: 1878 } },
  ],
  as_of: '2025-02-26',
  citation: {
    span_id: 'span-42',
    source_id: 'nvda_revenue_fy25',
    source_type: 'filing',
    label: 'NVDA 10-K FY25 Item 7',
    page: 42,
  },
};

const CHUNK: SourceChunk = {
  source_id: 'nvda_item1a_risk1',
  title: 'NVDA 10-K FY25 — Item 1A Risk Factors',
  filing_type: '10-K',
  filing_date: '2025-02-21',
  section: 'Item 1A',
  page: 12,
  text: 'Our success depends on continued demand for our GPU products... [truncated for test]',
  url: 'https://example.test/nvda/10-k/fy25',
};

export const handlers = [
  http.get('*/api/source_tables/:id', ({ params }) => {
    return HttpResponse.json({ ...TABLE, source_id: String(params.id) });
  }),
  http.get('*/api/source_chunk/:id', ({ params }) => {
    return HttpResponse.json({ ...CHUNK, source_id: String(params.id) });
  }),
  http.post('*/api/session/warm', () => {
    return new HttpResponse(null, { status: 204 });
  }),
];

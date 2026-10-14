/**
 * Vitest setup — runs once before each test file.
 * Starts the MSW worker so no real network calls leak out during tests.
 */

import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { server } from './msw-server';

// Provide a deterministic crypto.randomUUID in jsdom.
if (typeof crypto === 'undefined' || !crypto.randomUUID) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).crypto = {
    ...((globalThis as any).crypto ?? {}),
    randomUUID: () => '00000000-0000-4000-8000-000000000000',
  };
}

// Stub import.meta.env so service modules pick up test values.
vi.stubEnv('VITE_SF_LOGIN_URL', 'https://test.salesforce.com');
vi.stubEnv('VITE_SF_CLIENT_ID', 'test-client-id');
vi.stubEnv('VITE_SF_REDIRECT_URI', 'http://localhost:5173/callback');
vi.stubEnv('VITE_SF_AGENT_ID', 'test-agent-id');
vi.stubEnv('VITE_API_GATEWAY_URL', 'https://api.example.test');
vi.stubEnv('VITE_AWS_API_KEY', 'test-key');
vi.stubEnv('VITE_AGENT_ID', 'ir-research-orchestrator');
vi.stubEnv('VITE_ANYPOINT_VISUALIZER_URL', 'https://anypoint.example/visualizer');
vi.stubEnv('VITE_ANYPOINT_VISUALIZER_API', 'https://anypoint.example/api');
vi.stubEnv('VITE_ANYPOINT_ORG_ID', 'test-org');
vi.stubEnv('VITE_LANGFUSE_HOST', 'https://langfuse.example');
vi.stubEnv('VITE_LANGFUSE_PUBLIC_KEY', 'pk-test');

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

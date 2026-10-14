import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import { MockWebSocket } from './tests/mocks/mockWebSocket';

// Install our MockWebSocket as the global BEFORE any test imports kick in.
// We do NOT install MSW in the setup because MSW v2's WebSocket interceptor
// wraps the global WebSocket and prevents our mock from recording `send()`
// calls. REST calls in tests are stubbed per-test via fetch injection on the
// RestClient (see tests/mocks/restStub.ts).
Object.defineProperty(globalThis, 'WebSocket', {
  value: MockWebSocket,
  writable: true,
  configurable: true,
});

afterEach(() => {
  cleanup();
});

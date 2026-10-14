/**
 * MSW server for unit tests. Individual tests register their own handlers
 * via server.use(...) and beforeEach resets them.
 */

import { setupServer } from 'msw/node';

export const server = setupServer();

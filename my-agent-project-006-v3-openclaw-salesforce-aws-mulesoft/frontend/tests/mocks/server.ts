/**
 * MSW server for node/jsdom test runs. Intercepts all REST calls to the API
 * Gateway so tests run without a backend.
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);

/**
 * Zustand store for session identity and connection status.
 * Holds the IdP-derived token + principal + persona + correlation id. The
 * WebSocket client reads from here; components subscribe for reactive UI.
 */

import { create } from 'zustand';
import type { Persona } from '../types/persona';
import type { ConnectionStatus } from '../types/agent';

export interface SessionState {
  sessionToken: string | null;
  principalId: string | null;
  principalName: string | null;
  persona: Persona;
  sessionId: string | null;
  correlationId: string | null;
  connectionStatus: ConnectionStatus;

  setAuth: (p: {
    sessionToken: string;
    principalId: string;
    principalName: string;
    sessionId: string;
    correlationId: string;
  }) => void;
  setPersona: (p: Persona) => void;
  setConnectionStatus: (s: ConnectionStatus) => void;
  clearAuth: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionToken: null,
  principalId: null,
  principalName: null,
  persona: 'fsi_research',
  sessionId: null,
  correlationId: null,
  connectionStatus: 'idle',
  setAuth: (p) =>
    set({
      sessionToken: p.sessionToken,
      principalId: p.principalId,
      principalName: p.principalName,
      sessionId: p.sessionId,
      correlationId: p.correlationId,
    }),
  setPersona: (p) => set({ persona: p }),
  setConnectionStatus: (s) => set({ connectionStatus: s }),
  clearAuth: () =>
    set({
      sessionToken: null,
      principalId: null,
      principalName: null,
      sessionId: null,
      correlationId: null,
      connectionStatus: 'idle',
    }),
}));

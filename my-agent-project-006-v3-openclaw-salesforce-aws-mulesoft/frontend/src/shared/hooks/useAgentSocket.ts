/**
 * React hook wrapping the AgentSocket. One connection per persona per session;
 * the hook reads auth from Zustand and reflects the connection status back
 * into the same store so all components see a single source of truth.
 *
 * Also handles the session-token expiry hook — on 4401, we invoke the caller's
 * `onAuthExpired` which typically refreshes via the IdP and calls setAuth again.
 */

import { useEffect, useMemo, useRef } from 'react';
import { AgentSocket } from '../lib/wsClient';
import { HttpAgentTransport } from '../lib/httpAgentTransport';
import { useSessionStore } from '../store/session';
import type { InboundMessage, OutboundMessage } from '../types/agent';

export interface UseAgentSocketOptions {
  onMessage: (msg: InboundMessage) => void;
  onAuthExpired?: () => void;
  webSocketCtor?: typeof WebSocket;
}

export interface AgentSocketHandle {
  send: (msg: OutboundMessage) => void;
  close: () => void;
}

export function useAgentSocket(opts: UseAgentSocketOptions): AgentSocketHandle {
  const sessionToken = useSessionStore((s) => s.sessionToken);
  const persona = useSessionStore((s) => s.persona);
  const setConnectionStatus = useSessionStore((s) => s.setConnectionStatus);
  const handlerRef = useRef(opts.onMessage);
  handlerRef.current = opts.onMessage;
  const authExpiredRef = useRef(opts.onAuthExpired);
  authExpiredRef.current = opts.onAuthExpired;

  const agentcoreUrl = import.meta.env.VITE_AGENTCORE_URL ?? '';
  const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
  const longInvokeUrl = (import.meta.env.VITE_AGENT_LONG_URL ?? '') as string;
  const useHttp =
    (import.meta.env.VITE_AGENT_TRANSPORT ?? '').toLowerCase() === 'http' ||
    !agentcoreUrl ||
    !!apiUrl;

  const socket = useMemo(() => {
    if (!sessionToken) return null;
    if (useHttp && apiUrl) {
      return new HttpAgentTransport({
        apiUrl,
        sessionToken,
        persona,
        principalId: useSessionStore.getState().principalId ?? undefined,
        longInvokeUrl: longInvokeUrl || null,
      });
    }
    return new AgentSocket({
      agentcoreUrl,
      sessionToken,
      persona,
      tokenSupplier: () => useSessionStore.getState().sessionToken ?? '',
      onAuthExpired: () => authExpiredRef.current?.(),
      webSocketCtor: opts.webSocketCtor,
    });
    // Only rebuild on identity change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, persona, useHttp, apiUrl, agentcoreUrl, longInvokeUrl]);

  useEffect(() => {
    if (!socket) return;
    const offMsg = socket.onMessage((m) => handlerRef.current(m));
    const offStatus = socket.onStatus((s) => setConnectionStatus(s));
    socket.connect();
    return () => {
      offMsg();
      offStatus();
      socket.close();
    };
  }, [socket, setConnectionStatus]);

  return {
    send: (msg: OutboundMessage) => socket?.send(msg),
    close: () => socket?.close(),
  };
}

/* ── SSE Client for streaming agent responses via M6 gateway ── */

import { getAidToken } from "./gateway";

export interface SSECallbacks {
  onToken: (token: string) => void;
  onDetail: (type: string, payload: unknown) => void;
  onDone: () => void;
  onError: (error: string) => void;
  onBlocked: (reason: string) => void;
}

export function connectSSE(
  conversationId: string,
  messageContent: string,
  callbacks: SSECallbacks,
): { close: () => void } {
  const token = getAidToken();
  const params = new URLSearchParams({
    conversationId,
    content: messageContent,
  });
  if (token) {
    params.set("token", token);
  }

  const url = `/api/v1/chat/stream?${params.toString()}`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener("token", (e) => {
    callbacks.onToken(e.data);
  });

  eventSource.addEventListener("detail", (e) => {
    try {
      const parsed = JSON.parse(e.data) as { type: string; payload: unknown };
      callbacks.onDetail(parsed.type, parsed.payload);
    } catch {
      callbacks.onError("Failed to parse detail event");
    }
  });

  eventSource.addEventListener("done", () => {
    callbacks.onDone();
    eventSource.close();
  });

  eventSource.addEventListener("blocked", (e) => {
    callbacks.onBlocked(e.data);
    eventSource.close();
  });

  eventSource.addEventListener("error", () => {
    callbacks.onError("Connection lost. Reconnecting...");
  });

  return {
    close: () => eventSource.close(),
  };
}

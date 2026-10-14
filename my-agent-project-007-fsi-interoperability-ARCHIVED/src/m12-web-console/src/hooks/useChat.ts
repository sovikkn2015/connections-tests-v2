import { useState, useCallback, useRef } from "react";
import type { ChatMessage, DetailType } from "@/api/types";
import { connectSSE } from "@/api/sse";
import { mockChatMessages, mockMeetingPrep } from "@/mock/mockData";

const DEV_MODE = import.meta.env.DEV;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>(DEV_MODE ? mockChatMessages : []);
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [detailType, setDetailType] = useState<DetailType | null>(DEV_MODE ? "meeting_prep" : null);
  const [detailPayload, setDetailPayload] = useState<unknown>(DEV_MODE ? mockMeetingPrep : null);
  const [conversationId] = useState(() => crypto.randomUUID());
  const sseRef = useRef<{ close: () => void } | null>(null);

  const send = useCallback((content: string) => {
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);
    setStreamingContent("");

    if (DEV_MODE) {
      const mockResponse = "I'm processing your request. Here's what I found based on data from Salesforce FSC, Orion, and eMoney.";
      let i = 0;
      const interval = setInterval(() => {
        if (i < mockResponse.length) { setStreamingContent((prev) => prev + mockResponse[i]!); i++; }
        else {
          clearInterval(interval);
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(), role: "agent", specialist: "client_service", content: mockResponse,
            timestamp: new Date().toISOString(),
            sources: [{ name: "Salesforce FSC", module: "M11" }, { name: "Orion", module: "M11" }],
            provenanceTraceId: `e2e-${Date.now()}`, detailType: "meeting_prep",
          }]);
          setDetailType("meeting_prep");
          setDetailPayload(mockMeetingPrep);
          setStreaming(false);
          setStreamingContent("");
        }
      }, 20);
      return;
    }

    sseRef.current = connectSSE(conversationId, content, {
      onToken: (token) => setStreamingContent((prev) => prev + token),
      onDetail: (type, payload) => { setDetailType(type as DetailType); setDetailPayload(payload); },
      onDone: () => {
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "agent", specialist: "client_service", content: "", timestamp: new Date().toISOString() }]);
        setStreaming(false); setStreamingContent("");
      },
      onError: () => { setStreaming(false); setStreamingContent(""); },
      onBlocked: (reason) => {
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "system", content: reason || "This response was blocked by compliance review.", timestamp: new Date().toISOString() }]);
        setStreaming(false); setStreamingContent("");
      },
    });
  }, [conversationId]);

  return { messages, streaming, streamingContent, detailType, detailPayload, send };
}

import { useRef, useEffect } from "react";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { StreamingIndicator } from "./StreamingIndicator";
import type { ChatMessage as ChatMessageType } from "@/api/types";

interface Props {
  messages: ChatMessageType[];
  streaming: boolean;
  streamingContent: string;
  onSend: (content: string) => void;
  onViewProvenance?: (traceId: string) => void;
}

export function ChatPanel({ messages, streaming, streamingContent, onSend, onViewProvenance }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingContent]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && !streaming && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <p className="text-lg font-medium mb-2">Ask 007 anything</p>
            <p className="text-sm">Try: "Prep me for my meeting with Henderson tomorrow"</p>
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} onViewProvenance={onViewProvenance} />
        ))}
        {streaming && streamingContent && (
          <ChatMessage
            message={{ id: "streaming", role: "agent", specialist: "client_service", content: streamingContent, timestamp: new Date().toISOString() }}
          />
        )}
        {streaming && !streamingContent && <StreamingIndicator />}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={onSend} disabled={streaming} />
    </div>
  );
}

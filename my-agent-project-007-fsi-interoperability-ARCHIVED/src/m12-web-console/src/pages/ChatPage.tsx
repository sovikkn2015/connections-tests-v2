import { ChatPanel } from "@/components/chat/ChatPanel";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { useChat } from "@/hooks/useChat";
import * as gateway from "@/api/gateway";

export function ChatPage() {
  const { messages, streaming, streamingContent, detailType, detailPayload, send } = useChat();
  return (
    <div className="flex h-full">
      <div className="w-full md:w-2/5 border-r border-gray-200 dark:border-gray-700 flex flex-col">
        <ChatPanel messages={messages} streaming={streaming} streamingContent={streamingContent} onSend={send} />
      </div>
      <div className="hidden md:flex md:w-3/5 flex-col">
        <DetailPanel detailType={detailType} payload={detailPayload}
          onApproveOrder={(id) => void gateway.approveOrder(id)}
          onRejectOrder={(id, reason) => void gateway.rejectOrder(id, reason)} />
      </div>
    </div>
  );
}

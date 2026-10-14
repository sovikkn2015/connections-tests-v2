import { Bot, User, Shield, AlertTriangle, Link } from "lucide-react";
import { Badge } from "@/components/shared/Badge";
import type { ChatMessage as ChatMessageType } from "@/api/types";

interface Props {
  message: ChatMessageType;
  onViewProvenance?: (traceId: string) => void;
}

const specialistLabels: Record<string, string> = {
  client_service: "Client Service", research: "Research", execution: "Execution",
  onboarding: "Onboarding", compliance: "Compliance",
};

export function ChatMessage({ message, onViewProvenance }: Props) {
  const isUser = message.role === "user";
  const isHitl = message.role === "hitl";
  const isSystem = message.role === "system";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""} mb-4`}>
      <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? "bg-blue-100 dark:bg-blue-900/30" : isHitl ? "bg-yellow-100 dark:bg-yellow-900/30" : "bg-gray-100 dark:bg-gray-800"
      }`}>
        {isUser ? <User className="w-4 h-4 text-blue-700" aria-hidden="true" /> :
         isHitl ? <AlertTriangle className="w-4 h-4 text-yellow-700" aria-hidden="true" /> :
         isSystem ? <Shield className="w-4 h-4 text-gray-500" aria-hidden="true" /> :
         <Bot className="w-4 h-4 text-gray-600" aria-hidden="true" />}
      </div>
      <div className={`max-w-[75%] ${isUser ? "text-right" : ""}`}>
        {message.specialist && (
          <span className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">
            {specialistLabels[message.specialist] ?? message.specialist}
          </span>
        )}
        <div className={`rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? "bg-blue-800 text-white dark:bg-blue-700 rounded-br-sm" :
          isHitl ? "bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 text-gray-900 dark:text-gray-100 rounded-bl-sm" :
          "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm"
        }`}>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className={`flex items-center gap-2 mt-1 text-[10px] text-gray-400 dark:text-gray-500 ${isUser ? "justify-end" : ""}`}>
          <time>{new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
          {message.sources && message.sources.length > 0 && <span>· {message.sources.map((s) => s.name).join(", ")}</span>}
          {message.provenanceTraceId && onViewProvenance && (
            <button onClick={() => onViewProvenance(message.provenanceTraceId!)} className="inline-flex items-center gap-0.5 text-blue-600 dark:text-blue-400 hover:underline">
              <Link className="w-3 h-3" aria-hidden="true" />Provenance
            </button>
          )}
        </div>
        {message.hitlAction && (
          <div className="mt-2">
            <Badge variant={message.hitlAction.status === "approved" ? "success" : message.hitlAction.status === "rejected" ? "danger" : "warning"}>
              {message.hitlAction.status.toUpperCase()}
            </Badge>
          </div>
        )}
      </div>
    </div>
  );
}

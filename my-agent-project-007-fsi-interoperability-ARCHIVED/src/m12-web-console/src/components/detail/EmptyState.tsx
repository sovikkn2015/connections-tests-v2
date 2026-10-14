import { MessageSquare } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500 p-8">
      <MessageSquare className="w-12 h-12 mb-4 opacity-50" aria-hidden="true" />
      <p className="text-lg font-medium mb-1">No detail to show</p>
      <p className="text-sm text-center">Ask a question to get started. Contextual details will appear here.</p>
    </div>
  );
}

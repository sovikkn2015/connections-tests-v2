/**
 * WhatsApp-style chat bubble. No citations here — client channel strips them
 * per §1 client-liaison rules.
 */

import { stripCitations } from '../../../shared/lib/citationParser';

export interface ChatBubbleProps {
  from: 'client' | 'agent';
  text: string;
  timestamp: string;
}

export function ChatBubble({ from, text, timestamp }: ChatBubbleProps) {
  const displayText = from === 'agent' ? stripCitations(text) : text;
  return (
    <div className="client-bubble" data-from={from}>
      <div>{displayText}</div>
      <span className="client-bubble__meta">
        {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  );
}

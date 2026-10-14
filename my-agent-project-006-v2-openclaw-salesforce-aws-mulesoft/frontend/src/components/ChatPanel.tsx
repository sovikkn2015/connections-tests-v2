/**
 * Left panel — conversation with the FSI Research Agent via OpenClaw.
 * SLDS card with message list, sample queries, HITL prompts, and input field.
 */

import { useState, useRef, useEffect } from 'react';
import { useAgentStore } from '../store/agentStore';
import { extractTickers, detectRelevantTab } from '../services/responseParser';
import SampleQueries from './SampleQueries';
import HitlPanel from './HitlPanel';

export default function ChatPanel() {
  const {
    messages, isStreaming, connected, sendMessage, clearMessages,
    error, loadTickerData, setActiveTab, activeTicker, hitlGate,
  } = useAgentStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const sendingRef = useRef(false);

  // Only auto-scroll if user is near the bottom (within 100px)
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming || sendingRef.current) return;
    sendingRef.current = true;
    setInput('');
    const tickers = extractTickers(text.toUpperCase());
    if (tickers.length > 0) {
      loadTickerData(tickers[0]);
      const tab = detectRelevantTab(text);
      if (tab) setActiveTab(tab);
    }
    sendMessage(text).finally(() => { sendingRef.current = false; });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSampleSelect = (query: string) => {
    if (isStreaming) return;
    const tickers = extractTickers(query.toUpperCase());
    if (tickers.length > 0) {
      loadTickerData(tickers[0]);
      const tab = detectRelevantTab(query);
      if (tab) setActiveTab(tab);
    }
    sendMessage(query);
  };

  return (
    <article
      className="slds-card slds-grid slds-grid_vertical"
      style={{ height: '100%', margin: 0, borderRadius: 0, borderRight: '1px solid #d8dde6' }}
    >
      <div className="slds-card__header slds-grid slds-grid_align-spread slds-grid_vertical-align-center">
        <header className="slds-has-flexi-truncate">
          <h2 className="slds-card__header-title slds-text-heading_small">Agent Chat</h2>
          {activeTicker && (
            <p className="slds-text-body_small slds-text-color_weak">Researching: {activeTicker}</p>
          )}
        </header>
        <div>
          <button
            className="slds-button slds-button_neutral slds-button_small"
            onClick={clearMessages}
            disabled={isStreaming}
            aria-label="Clear messages"
          >
            Clear
          </button>
        </div>
      </div>

      {!connected && messages.length === 0 && (
        <div className="slds-card__body slds-card__body_inner slds-text-align_center slds-p-around_large">
          <p className="slds-text-body_regular slds-m-bottom_small">
            OpenClaw Gateway not connected. You can still explore seed data.
          </p>
          <p className="slds-text-body_small slds-text-color_weak">
            Try a sample query below to load research panel data.
          </p>
        </div>
      )}

      <div className="ir-chat-messages" ref={chatContainerRef} role="log" aria-label="Chat messages" aria-live="polite">
        {messages.map((msg) => (
          <div key={msg.id} className={msg.role === 'user' ? 'ir-msg-user' : 'ir-msg-agent'}>
            <div className={`ir-msg-bubble${msg.isStreaming ? ' ir-streaming-cursor' : ''}`}>
              {msg.text || (msg.isStreaming ? '' : '...')}
            </div>
          </div>
        ))}
        {hitlGate && <HitlPanel />}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="slds-notify slds-notify_alert slds-alert_error slds-m-horizontal_small" role="alert">
          <span className="slds-assistive-text">Error</span>
          <p className="slds-text-body_small">{error}</p>
        </div>
      )}

      <div className="ir-chat-input-area">
        <SampleQueries onSelect={handleSampleSelect} disabled={isStreaming} />
        <div className="slds-form-element">
          <div className="slds-form-element__control slds-input-has-fixed-addon">
            <div className="slds-grid slds-gutters_xx-small">
              <div className="slds-col slds-grow">
                <input
                  type="text"
                  className="slds-input"
                  placeholder="Ask the research agent..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isStreaming}
                  aria-label="Message input"
                />
              </div>
              <div className="slds-col slds-no-flex">
                <button
                  className="slds-button slds-button_brand"
                  onClick={handleSend}
                  disabled={!input.trim() || isStreaming}
                  aria-label="Send message"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

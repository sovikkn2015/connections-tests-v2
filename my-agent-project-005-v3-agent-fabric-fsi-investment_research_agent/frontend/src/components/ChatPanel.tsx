/**
 * Left panel — conversation with the IR Research Agent.
 * SLDS card with message list, sample queries, and input field.
 */

import { useState, useRef, useEffect } from 'react';
import { useAgentStore } from '../store/agentStore';
import { extractTickers, detectRelevantTab } from '../services/responseParser';
import SampleQueries from './SampleQueries';

/**
 * Parse live price data from agent response text and update the store.
 * Looks for patterns like "Price: $182.14" or "$182.1400" and
 * "Change: 0.9200 (0.5077%)" in the response.
 */
function updateFromResponse(text: string) {
  const { updatePriceFromResponse, companyData } = useAgentStore.getState();
  if (!companyData) return;

  // Match price patterns: "Price: $182.14" or "price: $182.1400" or standalone "$272.00"
  const priceMatch =
    text.match(/Price:\s*\$([0-9]+(?:\.[0-9]+)?)/i) ||
    text.match(/current(?:\s+market)?\s+price[^$]*\$([0-9]+(?:\.[0-9]+)?)/i) ||
    text.match(/trading\s+at\s+\$([0-9]+(?:\.[0-9]+)?)/i);

  if (!priceMatch) return;

  const price = parseFloat(priceMatch[1]);
  if (isNaN(price) || price <= 0) return;

  // Match change patterns: "Change: 0.9200 (0.5077%)" or "Change: -1.23 (-0.68%)"
  let change = 0;
  let changePct = 0;
  const changeMatch = text.match(/Change:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*\((-?[0-9]+(?:\.[0-9]+)?)%\)/i);
  if (changeMatch) {
    change = parseFloat(changeMatch[1]);
    changePct = parseFloat(changeMatch[2]);
  }

  updatePriceFromResponse(price, change, changePct);
}

export default function ChatPanel() {
  const {
    messages,
    isStreaming,
    sessionId,
    sendMessage,
    startNewSession,
    error,
    loadTickerData,
    setActiveTab,
    activeTicker,
  } = useAgentStore();


  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // When streaming finishes, try to parse live price data from the last agent message
  useEffect(() => {
    if (isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg.role === 'agent' && lastMsg.text) {
      updateFromResponse(lastMsg.text);
    }
  }, [isStreaming, messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
    // Auto-load ticker data when user mentions a ticker
    const tickers = extractTickers(text.toUpperCase());
    if (tickers.length > 0) {
      loadTickerData(tickers[0]);
      const tab = detectRelevantTab(text);
      if (tab) setActiveTab(tab);
    }
    sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSampleSelect = (query: string) => {
    if (isStreaming) return;
    // Auto-load ticker data when sample query mentions a ticker
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
      style={{
        height: '100%',
        margin: 0,
        borderRadius: 0,
        borderRight: '1px solid #d8dde6',
      }}
    >
      {/* Card Header */}
      <div className="slds-card__header slds-grid slds-grid_align-spread slds-grid_vertical-align-center">
        <header className="slds-has-flexi-truncate">
          <h2 className="slds-card__header-title slds-text-heading_small">
            Agent Chat
          </h2>
          {activeTicker && (
            <p className="slds-text-body_small slds-text-color_weak">
              Researching: {activeTicker}
            </p>
          )}
        </header>
        <div>
          <button
            className="slds-button slds-button_neutral slds-button_small"
            onClick={startNewSession}
            disabled={isStreaming}
            aria-label="Start new session"
          >
            New Session
          </button>
        </div>
      </div>

      {/* No session prompt */}
      {!sessionId && (
        <div className="slds-card__body slds-card__body_inner slds-text-align_center slds-p-around_large">
          <p className="slds-text-body_regular slds-m-bottom_medium">
            Click "New Session" to start chatting with the IR Research Agent.
          </p>
        </div>
      )}

      {/* Messages */}
      {sessionId && (
        <div className="ir-chat-messages" role="log" aria-label="Chat messages" aria-live="polite">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={msg.role === 'user' ? 'ir-msg-user' : 'ir-msg-agent'}
            >
              <div
                className={`ir-msg-bubble${msg.isStreaming ? ' ir-streaming-cursor' : ''}`}
              >
                {msg.text || (msg.isStreaming ? '' : '...')}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="slds-notify slds-notify_alert slds-alert_error slds-m-horizontal_small" role="alert">
          <span className="slds-assistive-text">Error</span>
          <p className="slds-text-body_small">{error}</p>
        </div>
      )}

      {/* Sample queries + input */}
      {sessionId && (
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
      )}
    </article>
  );
}

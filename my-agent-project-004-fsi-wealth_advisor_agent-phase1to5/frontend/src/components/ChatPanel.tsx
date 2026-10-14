/**
 * Left panel — conversation with the Wealth Advisor Agent.
 * SLDS card with message list, categorized sample queries, and input field.
 */

import { useState, useRef, useEffect } from 'react';
import { useAgentStore } from '../store/agentStore';
import SampleQueries from './SampleQueries';

export default function ChatPanel() {
  const {
    messages,
    isStreaming,
    sessionId,
    sendMessage,
    startNewSession,
    error,
    activeName,
  } = useAgentStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
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
          {activeName && (
            <p className="slds-text-body_small slds-text-color_weak">
              Discussing: {activeName}
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
            Click &quot;New Session&quot; to start chatting with the Wealth Advisor Agent.
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
                    placeholder="Ask the wealth advisor agent..."
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

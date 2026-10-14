/**
 * HITL (Human-in-the-Loop) Panel — renders when pipeline hits a gate stage.
 * Shows context, options (Approve/Reject/Edit/Collaborate).
 * Edit: shows textarea for editing content before continuing.
 * Collaborate: opens mini-chat for back-and-forth with the agent.
 */

import { useState } from 'react';
import { useAgentStore } from '../store/agentStore';
import * as openclawApi from '../services/openclawApi';

type HitlMode = 'actions' | 'edit' | 'collaborate';

export default function HitlPanel() {
  const { hitlGate, approveHitlGate, rejectHitlGate, sessionKey } = useAgentStore();
  const [mode, setMode] = useState<HitlMode>('actions');
  const [editContent, setEditContent] = useState('');
  const [collabInput, setCollabInput] = useState('');
  const [collabMessages, setCollabMessages] = useState<{ role: 'user' | 'agent'; text: string }[]>([]);
  const [sending, setSending] = useState(false);

  if (!hitlGate) return null;

  const handleEditStart = () => {
    setEditContent(hitlGate.context || '');
    setMode('edit');
  };

  const handleEditSubmit = async () => {
    setSending(true);
    try {
      await openclawApi.sendMessage(
        `[HITL Edit] Stage ${hitlGate.stageId} (${hitlGate.stageName}): Edited content:\n${editContent}`,
        sessionKey, 'fsi-research',
        { onText: () => {}, onToolStart: () => {}, onToolResult: () => {},
          onToolError: () => {}, onLifecycle: () => {}, onComplete: () => {} },
      );
      approveHitlGate();
    } catch { approveHitlGate(); }
    finally { setSending(false); setMode('actions'); }
  };

  const handleCollabStart = () => {
    setCollabMessages([]);
    setCollabInput('');
    setMode('collaborate');
  };

  const handleCollabSend = async () => {
    const text = collabInput.trim();
    if (!text || sending) return;
    setCollabInput('');
    setCollabMessages((prev) => [...prev, { role: 'user', text }]);
    setSending(true);

    let agentReply = '';
    try {
      await openclawApi.sendMessage(
        `[HITL Collaborate] Stage ${hitlGate.stageId} (${hitlGate.stageName}): ${text}`,
        sessionKey, 'fsi-research',
        {
          onText: (chunk: string) => { agentReply += chunk; },
          onToolStart: () => {},
          onToolResult: () => {},
          onToolError: () => {},
          onLifecycle: () => {},
          onComplete: () => {
            setCollabMessages((prev) => [...prev, { role: 'agent', text: agentReply || 'Done.' }]);
          },
        },
      );
    } catch (err) {
      setCollabMessages((prev) => [...prev, { role: 'agent', text: `Error: ${(err as Error).message}` }]);
    } finally {
      setSending(false);
    }
  };

  const handleCollabDone = () => {
    approveHitlGate();
    setMode('actions');
  };

  return (
    <div className="ir-hitl-panel" role="alert" aria-label="Human-in-the-loop gate">
      <div className="slds-grid slds-grid_vertical-align-center slds-m-bottom_x-small">
        <span style={{ fontSize: '1.25rem', marginRight: '0.5rem' }} aria-hidden="true">{'\u2298'}</span>
        <div>
          <p className="slds-text-body_regular" style={{ fontWeight: 600 }}>
            HITL Gate: {hitlGate.stageName}
          </p>
          <p className="slds-text-body_small slds-text-color_weak">
            Stage {hitlGate.stageId} requires your review before proceeding.
          </p>
        </div>
      </div>

      {hitlGate.context && mode === 'actions' && (
        <p className="slds-text-body_small slds-m-bottom_small" style={{ background: '#fff', padding: '0.5rem', borderRadius: 4 }}>
          {hitlGate.context}
        </p>
      )}

      {/* Edit Mode */}
      {mode === 'edit' && (
        <div className="slds-m-bottom_small">
          <textarea
            className="slds-textarea" value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            rows={6} aria-label="Edit gate content" disabled={sending}
          />
          <div className="slds-m-top_x-small">
            <button className="slds-button slds-button_brand slds-button_small" onClick={handleEditSubmit} disabled={sending}>
              {sending ? 'Submitting\u2026' : 'Submit Edit & Continue'}
            </button>
            <button className="slds-button slds-button_neutral slds-button_small slds-m-left_x-small" onClick={() => setMode('actions')} disabled={sending}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Collaborate Mode */}
      {mode === 'collaborate' && (
        <div className="slds-m-bottom_small">
          <div style={{ maxHeight: 150, overflow: 'auto', background: '#fff', borderRadius: 4, padding: '0.5rem', marginBottom: '0.5rem' }}>
            {collabMessages.length === 0 && (
              <p className="slds-text-body_small slds-text-color_weak">Ask the agent a question about this gate.</p>
            )}
            {collabMessages.map((m, i) => (
              <p key={i} className="slds-text-body_small" style={{ marginBottom: 4 }}>
                <strong>{m.role === 'user' ? 'You' : 'Agent'}:</strong> {m.text}
              </p>
            ))}
          </div>
          <div className="slds-grid slds-gutters_xx-small">
            <div className="slds-col slds-grow">
              <input
                type="text" className="slds-input" placeholder="Ask the agent..."
                value={collabInput} onChange={(e) => setCollabInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleCollabSend(); } }}
                disabled={sending} aria-label="Collaborate message input"
              />
            </div>
            <div className="slds-col slds-no-flex">
              <button className="slds-button slds-button_brand slds-button_small" onClick={handleCollabSend} disabled={sending || !collabInput.trim()}>
                Send
              </button>
            </div>
          </div>
          <button className="slds-button slds-button_success slds-button_small slds-m-top_x-small" onClick={handleCollabDone}>
            Done &mdash; Approve &amp; Continue
          </button>
        </div>
      )}

      {/* Action Buttons */}
      {mode === 'actions' && (
        <div className="slds-button-group" role="group" aria-label="Gate actions">
          {hitlGate.options.includes('approve') && (
            <button className="slds-button slds-button_success slds-button_small" onClick={approveHitlGate} aria-label="Approve and continue pipeline">
              Approve
            </button>
          )}
          {hitlGate.options.includes('reject') && (
            <button className="slds-button slds-button_destructive slds-button_small" onClick={rejectHitlGate} aria-label="Reject and stop pipeline">
              Reject
            </button>
          )}
          {hitlGate.options.includes('edit') && (
            <button className="slds-button slds-button_neutral slds-button_small" onClick={handleEditStart} aria-label="Edit and continue">
              Edit &amp; Continue
            </button>
          )}
          {hitlGate.options.includes('collaborate') && (
            <button className="slds-button slds-button_neutral slds-button_small" onClick={handleCollabStart} aria-label="Collaborate with agent">
              Collaborate
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Bottom collapsible panel — Langfuse trace timeline.
 * Shows a placeholder that links to the Langfuse dashboard.
 */

import { useAgentStore } from '../store/agentStore';

const LANGFUSE_HOST = import.meta.env.VITE_LANGFUSE_HOST || 'https://us.cloud.langfuse.com';

export default function TracePanel() {
  const { traceExpanded, toggleTrace } = useAgentStore();

  return (
    <div
      className="ir-trace-panel"
      style={{ height: traceExpanded ? '12rem' : '2rem' }}
    >
      {/* Toggle bar */}
      <div
        className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-horizontal_small"
        style={{
          height: '2rem',
          background: '#f3f3f3',
          cursor: 'pointer',
          borderTop: '1px solid #d8dde6',
        }}
        onClick={toggleTrace}
        role="button"
        tabIndex={0}
        aria-expanded={traceExpanded}
        aria-label="Toggle trace panel"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleTrace();
          }
        }}
      >
        <span className="slds-text-body_small slds-text-color_weak">
          Langfuse Trace Timeline
        </span>
        <span className="slds-text-body_small slds-text-color_weak">
          {traceExpanded ? '▼' : '▲'}
        </span>
      </div>

      {/* Trace content */}
      {traceExpanded && (
        <div className="slds-p-around_small" style={{ overflow: 'auto', height: 'calc(100% - 2rem)' }}>
          <div className="slds-grid slds-grid_vertical-align-center slds-grid_align-center" style={{ height: '100%' }}>
            <div className="slds-text-align_center">
              <p className="slds-text-body_regular slds-text-color_weak slds-m-bottom_small">
                Agent traces are logged to Langfuse for observability and governance.
              </p>
              <a
                href={LANGFUSE_HOST}
                target="_blank"
                rel="noopener noreferrer"
                className="slds-button slds-button_neutral slds-button_small"
              >
                Open Langfuse Dashboard
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

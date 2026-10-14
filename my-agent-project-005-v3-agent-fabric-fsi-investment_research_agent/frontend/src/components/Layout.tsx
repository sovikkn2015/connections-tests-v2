/**
 * Full-page SLDS layout.
 * Global header + three-panel workspace:
 *   Chat (left 40%) | Research or Visualizer (right 60%)
 *   Trace (bottom collapsible)
 *
 * V3: A small toggle in the right-panel header flips between the classic
 * Research view and the new Agent Visualizer. Research is the default so V2
 * parity is preserved.
 */

import GlobalHeader from './GlobalHeader';
import ChatPanel from './ChatPanel';
import ResearchPanel from './ResearchPanel';
import TracePanel from './TracePanel';
import AgentVisualizer from './AgentVisualizer';
import { useAgentStore } from '../store/agentStore';

function RightPanelToggle() {
  const { rightPanelView, setRightPanelView } = useAgentStore();
  const mkBtn = (view: 'research' | 'visualizer', label: string) => (
    <button
      key={view}
      type="button"
      role="tab"
      aria-selected={rightPanelView === view}
      aria-controls={`right-panel-${view}`}
      className={`slds-button ${rightPanelView === view ? 'slds-button_brand' : 'slds-button_neutral'}`}
      onClick={() => setRightPanelView(view)}
    >
      {label}
    </button>
  );
  return (
    <div
      className="slds-button-group slds-m-around_x-small"
      role="tablist"
      aria-label="Switch right panel view"
    >
      {mkBtn('research', 'Research')}
      {mkBtn('visualizer', 'Agent Visualizer')}
    </div>
  );
}

export default function Layout() {
  const { rightPanelView } = useAgentStore();

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <GlobalHeader />
      <div className="ir-workspace">
        <div className="ir-main-panels">
          {/* Left: Chat — 40% */}
          <div
            className="slds-col"
            style={{ width: '40%', minWidth: '20rem', height: '100%' }}
          >
            <ChatPanel />
          </div>
          {/* Right: Research or Visualizer — 60% */}
          <div
            className="slds-col"
            style={{
              width: '60%',
              height: '100%',
              background: '#f4f6f9',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                borderBottom: '1px solid #d8dde6',
                background: '#ffffff',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <RightPanelToggle />
            </div>
            <div
              id={`right-panel-${rightPanelView}`}
              role="tabpanel"
              aria-labelledby={rightPanelView}
              style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}
            >
              {rightPanelView === 'research' ? <ResearchPanel /> : <AgentVisualizer />}
            </div>
          </div>
        </div>
        <TracePanel />
      </div>
    </div>
  );
}

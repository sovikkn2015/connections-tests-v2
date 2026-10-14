/**
 * Full-page SLDS layout.
 * Global header + three-panel workspace:
 *   Chat (left 40%) | Research (right 60%)
 *   Trace (bottom collapsible)
 */

import GlobalHeader from './GlobalHeader';
import ChatPanel from './ChatPanel';
import ResearchPanel from './ResearchPanel';
import TracePanel from './TracePanel';

export default function Layout() {
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
          {/* Right: Research — 60% */}
          <div
            className="slds-col"
            style={{ width: '60%', height: '100%', background: '#f4f6f9' }}
          >
            <ResearchPanel />
          </div>
        </div>
        <TracePanel />
      </div>
    </div>
  );
}

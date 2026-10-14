/**
 * Full-page SLDS layout.
 * Global header + three-panel workspace:
 *   Chat (left 40%) | Advisor (right 60%)
 *   Trace (bottom collapsible)
 */

import GlobalHeader from './GlobalHeader';
import ChatPanel from './ChatPanel';
import AdvisorPanel from './AdvisorPanel';
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
          {/* Right: Advisor — 60% */}
          <div
            className="slds-col"
            style={{ width: '60%', height: '100%', background: '#f4f6f9' }}
          >
            <AdvisorPanel />
          </div>
        </div>
        <TracePanel />
      </div>
    </div>
  );
}

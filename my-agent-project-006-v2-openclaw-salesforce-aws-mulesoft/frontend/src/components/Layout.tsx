/**
 * Full-page SLDS layout with PipelineTracker.
 * Global header + Pipeline Tracker + three-panel workspace:
 *   Chat (left 40%) | Research (right 60%)
 *   Trace (bottom collapsible)
 */

import GlobalHeader from './GlobalHeader';
import ChatPanel from './ChatPanel';
import ResearchPanel from './ResearchPanel';
import PipelineTracker from './PipelineTracker';
import TracePanel from './TracePanel';
import MuleSoftHitlPanel from './MuleSoftHitlPanel';

export default function Layout() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <GlobalHeader />
      <PipelineTracker />
      <div className="ir-workspace">
        <div className="ir-main-panels">
          <div className="slds-col" style={{ width: '40%', minWidth: '20rem', height: '100%' }}>
            <ChatPanel />
          </div>
          <div className="slds-col" style={{ width: '60%', height: '100%', background: '#f4f6f9' }}>
            <ResearchPanel />
          </div>
        </div>
        <TracePanel />
      </div>
      {/*
        MuleSoft HITL approval dialog — mounted at the top level so it
        overlays the entire workspace regardless of which sub-view the
        user is currently interacting with. Renders null when no
        `hitl.pending` event is in flight.
      */}
      <MuleSoftHitlPanel />
    </div>
  );
}

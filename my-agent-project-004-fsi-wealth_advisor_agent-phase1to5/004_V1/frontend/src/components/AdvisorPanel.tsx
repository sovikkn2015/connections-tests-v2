/**
 * Right panel — structured advisor output with SLDS tabs.
 * Tabs: Clients | Portfolio | Goals | Activity
 * Empty states shown until agent responds with relevant data.
 */

import { useAgentStore } from '../store/agentStore';
import type { AdvisorTab } from '../types';

export default function AdvisorPanel() {
  const { activeTab, setActiveTab, activeName } = useAgentStore();

  const tabs: { id: AdvisorTab; label: string; hasData: boolean }[] = [
    { id: 'clients', label: 'Clients', hasData: false },
    { id: 'portfolio', label: 'Portfolio', hasData: false },
    { id: 'goals', label: 'Goals', hasData: false },
    { id: 'activity', label: 'Activity', hasData: false },
  ];

  return (
    <div
      className="slds-grid slds-grid_vertical"
      style={{ height: '100%', overflow: 'hidden' }}
    >
      {/* Active Client Header */}
      {activeName && (
        <div
          className="slds-text-body_small slds-text-color_weak"
          style={{ background: '#eef4ff', padding: '4px 12px' }}
        >
          Viewing: {activeName}
        </div>
      )}

      {/* SLDS Tabs with dot indicators */}
      <div className="slds-tabs_default">
        <ul className="slds-tabs_default__nav" role="tablist">
          {tabs.map((tab) => (
            <li
              key={tab.id}
              className={`slds-tabs_default__item${activeTab === tab.id ? ' slds-is-active' : ''}`}
              role="presentation"
            >
              <a
                className="slds-tabs_default__link"
                href="#"
                role="tab"
                aria-selected={activeTab === tab.id}
                aria-controls={`tab-panel-${tab.id}`}
                id={`tab-${tab.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  setActiveTab(tab.id);
                }}
              >
                {tab.label}
                {tab.hasData && (
                  <span
                    className="ir-tab-dot"
                    aria-label={`${tab.label} has data`}
                    style={{
                      display: 'inline-block',
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: '#04844b',
                      marginLeft: 6,
                    }}
                  />
                )}
              </a>
            </li>
          ))}
        </ul>
      </div>

      {/* Tab Content */}
      <div className="ir-research-content" style={{ flex: 1, overflow: 'auto' }}>
        {activeTab === 'clients' && (
          <div role="tabpanel" id="tab-panel-clients" aria-labelledby="tab-clients">
            <EmptyState message="Ask about a client to see their 360° view here." />
          </div>
        )}
        {activeTab === 'portfolio' && (
          <div role="tabpanel" id="tab-panel-portfolio" aria-labelledby="tab-portfolio">
            <EmptyState message="Ask about a portfolio to see allocation and returns." />
          </div>
        )}
        {activeTab === 'goals' && (
          <div role="tabpanel" id="tab-panel-goals" aria-labelledby="tab-goals">
            <EmptyState message="Ask about financial goals to see progress tracking." />
          </div>
        )}
        {activeTab === 'activity' && (
          <div role="tabpanel" id="tab-panel-activity" aria-labelledby="tab-activity">
            <EmptyState message="Ask about transactions, meetings, or compliance to see activity." />
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="slds-p-around_large slds-text-align_center">
      <div className="slds-illustration slds-illustration_small">
        <p className="slds-text-body_regular slds-text-color_weak slds-m-top_medium">
          {message}
        </p>
      </div>
    </div>
  );
}

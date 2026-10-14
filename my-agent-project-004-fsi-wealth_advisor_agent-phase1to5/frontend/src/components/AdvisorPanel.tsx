/**
 * Right panel — Salesforce Lightning-style advisor workbench.
 * Tabs: Clients | Portfolio | Goals | Activity
 * Renders agent response text in rich SLDS cards with proper formatting.
 * Parses structured sections from agent output (bullet points, headers, etc.)
 */

import { useAgentStore } from '../store/agentStore';
import type { AdvisorTab } from '../types';

export default function AdvisorPanel() {
  const { activeTab, setActiveTab, activeName, tabResponses } = useAgentStore();

  const tabs: { id: AdvisorTab; label: string }[] = [
    { id: 'clients', label: 'Clients' },
    { id: 'portfolio', label: 'Portfolio' },
    { id: 'goals', label: 'Goals' },
    { id: 'activity', label: 'Activity' },
  ];

  const agentText = tabResponses[activeTab] || '';

  return (
    <div className="slds-grid slds-grid_vertical" style={{ height: '100%', overflow: 'hidden' }}>
      {activeName && (
        <div className="wa-record-header">
          <div className="wa-record-header__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="#fff"/>
            </svg>
          </div>
          <div className="wa-record-header__info">
            <span className="wa-record-header__label">Household</span>
            <span className="wa-record-header__name">{activeName}</span>
          </div>
        </div>
      )}
      <div className="slds-tabs_default">
        <ul className="slds-tabs_default__nav" role="tablist">
          {tabs.map((tab) => (
            <li key={tab.id} className={`slds-tabs_default__item${activeTab === tab.id ? ' slds-is-active' : ''}`} role="presentation">
              <a className="slds-tabs_default__link" href="#" role="tab" aria-selected={activeTab === tab.id}
                onClick={(e) => { e.preventDefault(); setActiveTab(tab.id); }}>
                {tab.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="wa-panel-content">
        {!agentText ? <EmptyState tab={activeTab} /> : <AgentResponseCard text={agentText} tab={activeTab} />}
      </div>
    </div>
  );
}


const EMPTY_MESSAGES: Record<AdvisorTab, { title: string; subtitle: string }> = {
  clients: { title: 'No Client Selected', subtitle: 'Ask about a client to see their 360° view here.' },
  portfolio: { title: 'No Portfolio Data', subtitle: 'Ask about a portfolio to see allocation, returns, and rebalancing.' },
  goals: { title: 'No Goals Loaded', subtitle: 'Ask about financial goals to see progress tracking.' },
  activity: { title: 'No Activity Yet', subtitle: 'Ask about meetings, transactions, compliance, or referrals.' },
};

function EmptyState({ tab }: { tab: AdvisorTab }) {
  const cfg = EMPTY_MESSAGES[tab];
  return (
    <div className="wa-empty-state">
      <h3 className="wa-empty-state__title">{cfg.title}</h3>
      <p className="wa-empty-state__subtitle">{cfg.subtitle}</p>
    </div>
  );
}

const TAB_TITLES: Record<AdvisorTab, string> = {
  clients: 'Client Summary',
  portfolio: 'Portfolio Analysis',
  goals: 'Goal Progress',
  activity: 'Activity Feed',
};

function AgentResponseCard({ text, tab }: { text: string; tab: AdvisorTab }) {
  const sections = parseAgentSections(text);
  return (
    <div className="slds-p-around_small">
      <article className="slds-card wa-response-card">
        <div className="slds-card__header slds-grid slds-grid_align-spread">
          <header className="slds-has-flexi-truncate">
            <h2 className="slds-card__header-title">
              <span className="slds-text-heading_small">{TAB_TITLES[tab]}</span>
            </h2>
          </header>
          <div className="wa-card-timestamp">
            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
        <div className="slds-card__body slds-card__body_inner">
          {sections.length > 0 ? (
            sections.map((section, i) => <ResponseSection key={i} section={section} />)
          ) : (
            <p className="slds-text-body_regular wa-response-text">{text}</p>
          )}
        </div>
      </article>
    </div>
  );
}

interface ParsedSection {
  type: 'header' | 'keyvalue' | 'bullet' | 'text' | 'divider';
  label?: string;
  value?: string;
  items?: string[];
  text?: string;
}

function parseAgentSections(text: string): ParsedSection[] {
  const sections: ParsedSection[] = [];
  const lines = text.split('\n');
  let currentBullets: string[] = [];
  const flushBullets = () => {
    if (currentBullets.length > 0) {
      sections.push({ type: 'bullet', items: [...currentBullets] });
      currentBullets = [];
    }
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) { flushBullets(); continue; }
    if (trimmed.startsWith('##') || (trimmed.startsWith('**') && trimmed.endsWith('**'))) {
      flushBullets();
      sections.push({ type: 'header', text: trimmed.replace(/^#+\s*/, '').replace(/\*\*/g, '') });
      continue;
    }
    if (/^[-=]{3,}$/.test(trimmed)) { flushBullets(); sections.push({ type: 'divider' }); continue; }
    const kvMatch = trimmed.match(/^\*?\*?([^:*]+)\*?\*?:\s*(.+)$/);
    if (kvMatch && kvMatch[1].length < 40 && !trimmed.startsWith('-') && !trimmed.startsWith('•')) {
      flushBullets();
      sections.push({ type: 'keyvalue', label: kvMatch[1].trim(), value: kvMatch[2].trim() });
      continue;
    }
    if (trimmed.startsWith('-') || trimmed.startsWith('•') || (trimmed.startsWith('*') && !trimmed.startsWith('**'))) {
      currentBullets.push(trimmed.replace(/^[-•*]\s*/, ''));
      continue;
    }
    flushBullets();
    sections.push({ type: 'text', text: trimmed });
  }
  flushBullets();
  return sections;
}

function ResponseSection({ section }: { section: ParsedSection }) {
  switch (section.type) {
    case 'header': return <h3 className="wa-section-header">{section.text}</h3>;
    case 'divider': return <hr className="wa-section-divider" />;
    case 'keyvalue': return (
      <div className="wa-kv-row">
        <span className="wa-kv-label">{section.label}</span>
        <span className="wa-kv-value">{section.value}</span>
      </div>
    );
    case 'bullet': return (
      <ul className="wa-bullet-list">
        {section.items?.map((item, i) => <li key={i} className="wa-bullet-item">{item}</li>)}
      </ul>
    );
    case 'text': return <p className="wa-section-text">{section.text}</p>;
    default: return null;
  }
}

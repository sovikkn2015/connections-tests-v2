/**
 * Right panel — structured research output with SLDS tabs.
 * Tabs: Company, Coverage, Analysis, Filings
 * Enhanced with tab dot indicators, active ticker header, and rich filings view.
 */

import { useAgentStore } from '../store/agentStore';
import type { ResearchTab, FilingFilter } from '../types';
import CompanyCard from './CompanyCard';
import CoverageTable from './CoverageTable';
import FinancialChart from './FinancialChart';

const FILING_FILTERS: FilingFilter[] = ['All', '10-K', '10-Q', '8-K', 'DEF 14A'];

const FILING_TYPE_COLORS: Record<string, string> = {
  '10-K': '#1589ee',
  '10-Q': '#04844b',
  '8-K': '#e87400',
  'DEF 14A': '#9050e9',
};

export default function ResearchPanel() {
  const {
    activeTab,
    setActiveTab,
    filings,
    companyData,
    coverageData,
    chartData,
    valuationData,
    activeTicker,
    filingFilter,
    setFilingFilter,
  } = useAgentStore();

  const tabs: { id: ResearchTab; label: string; hasData: boolean }[] = [
    { id: 'company', label: 'Company', hasData: !!companyData },
    { id: 'coverage', label: 'Coverage', hasData: coverageData.length > 0 },
    {
      id: 'analysis',
      label: 'Analysis',
      hasData: chartData.length > 0 || !!valuationData,
    },
    { id: 'filings', label: 'Filings', hasData: filings.length > 0 },
  ];

  const filteredFilings =
    filingFilter === 'All'
      ? filings
      : filings.filter((f) => f.type === filingFilter);

  return (
    <div
      className="slds-grid slds-grid_vertical"
      style={{ height: '100%', overflow: 'hidden' }}
    >
      {/* Active Ticker Header */}
      {activeTicker && companyData && (
        <div
          className="slds-text-body_small slds-text-color_weak"
          style={{ background: '#eef4ff', padding: '4px 12px' }}
        >
          Researching: {companyData.name} ({activeTicker})
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
        {activeTab === 'company' && (
          <div role="tabpanel" id="tab-panel-company" aria-labelledby="tab-company">
            <CompanyCard />
          </div>
        )}
        {activeTab === 'coverage' && (
          <div role="tabpanel" id="tab-panel-coverage" aria-labelledby="tab-coverage">
            <CoverageTable />
          </div>
        )}
        {activeTab === 'analysis' && (
          <div role="tabpanel" id="tab-panel-analysis" aria-labelledby="tab-analysis">
            <FinancialChart />
          </div>
        )}
        {activeTab === 'filings' && (
          <div role="tabpanel" id="tab-panel-filings" aria-labelledby="tab-filings">
            {/* Filing filter chips */}
            <div className="slds-p-around_small">
              <div className="slds-button-group" role="group" aria-label="Filter filings by type">
                {FILING_FILTERS.map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    className={`slds-button ${filingFilter === filter ? 'slds-button_brand' : 'slds-button_neutral'}`}
                    onClick={() => setFilingFilter(filter)}
                    aria-pressed={filingFilter === filter}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* Filtered filings list */}
            <FilingsList filings={filteredFilings} activeFilter={filingFilter} />
          </div>
        )}
      </div>
    </div>
  );
}

function FilingsList({
  filings,
  activeFilter,
}: {
  filings: { type: string; date: string; description: string; url: string; aiSummary?: string }[];
  activeFilter: string;
}) {
  if (!filings || filings.length === 0) {
    const msg =
      activeFilter === 'All'
        ? 'Ask "Show me NVDA 10-K" to see SEC filings.'
        : `No ${activeFilter} filings found. Try selecting "All" or a different type.`;
    return (
      <div className="slds-p-around_large slds-text-align_center">
        <p className="slds-text-body_regular slds-text-color_weak">
          {msg}
        </p>
      </div>
    );
  }

  return (
    <div className="slds-p-horizontal_small slds-p-bottom_small">
      {filings.map((f, i) => {
        const badgeColor = FILING_TYPE_COLORS[f.type] || '#706e6b';
        return (
          <article
            key={i}
            className="ir-filing-card slds-card slds-m-bottom_small"
          >
            <div className="slds-card__body slds-card__body_inner">
              <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center">
                <div className="slds-col">
                  <span
                    className="slds-badge"
                    style={{
                      background: badgeColor,
                      color: '#fff',
                      marginRight: 8,
                    }}
                  >
                    {f.type}
                  </span>
                  <span className="slds-text-body_regular">{f.description}</span>
                </div>
                <div className="slds-col slds-no-flex slds-text-body_small slds-text-color_weak">
                  {f.date}
                </div>
              </div>

              {f.aiSummary && (
                <p
                  className="slds-text-body_small slds-m-top_x-small"
                  style={{ fontStyle: 'italic', fontSize: '0.8125rem', color: '#514f4d' }}
                >
                  {f.aiSummary}
                </p>
              )}

              {f.url && (
                <a
                  href={f.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="slds-text-link slds-text-body_small slds-m-top_x-small"
                  style={{ display: 'inline-block' }}
                >
                  View on SEC EDGAR ↗
                </a>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

/**
 * Categorized, collapsible sample queries for the Investment Research Agent.
 *
 * Categories reflect the 10 Apex InvocableActions wired into the backend.
 * Queries span 7 tickers (NVDA, AAPL, MSFT, TSLA, GOOGL, AMZN, META) so the
 * tester can see the agent handle variety rather than only NVDA.
 *
 * Pattern mirrors the 004 Wealth Advisor Workbench: first 3 categories
 * expanded by default, rest collapsed — click the heading to toggle.
 */

import { useState } from 'react';

const SAMPLE_CATEGORIES = [
  {
    label: 'Company Lookup',
    queries: [
      'Tell me about NVDA',
      'Look up AAPL',
      'What is Microsoft',
      'Describe Tesla',
      'Tell me about GOOGL',
    ],
  },
  {
    label: 'Analyst Coverage',
    queries: [
      'Who covers NVDA',
      'Analyst ratings for AAPL',
      'Show me coverage for TSLA',
      'Analyst consensus for GOOGL',
      'Coverage details for MSFT',
    ],
  },
  {
    label: 'Sentiment',
    queries: [
      "What's the sentiment on NVDA",
      'Is Tesla bullish or bearish',
      'Sentiment analysis for AAPL',
      'Is GOOGL positive or negative',
    ],
  },
  {
    label: 'Market Data',
    queries: [
      'NVDA quote',
      'What is the price of AAPL',
      'TSLA price history for 30 days',
      'MSFT current price',
      'AMZN market data',
    ],
  },
  {
    label: 'SEC Filings',
    queries: [
      'NVDA latest 10-K filing',
      'Show me Apple 10-Q',
      'Microsoft 8-K filings',
      'Tesla recent SEC filings',
      'GOOGL 10-K',
    ],
  },
  {
    label: 'Earnings',
    queries: [
      'When does NVDA report earnings',
      'Earnings calendar for AAPL',
      'Next earnings for TSLA',
      'MSFT upcoming earnings date',
    ],
  },
  {
    label: 'News',
    queries: [
      'Latest news on Tesla',
      'Headlines for Apple',
      'Recent news for NVDA',
      'News about META',
    ],
  },
  {
    label: 'Valuation',
    queries: [
      'DCF valuation for NVDA',
      'Fair value for AAPL',
      'Monte Carlo analysis on GOOGL',
      'Comps-based valuation for MSFT',
      'Price target vs fair value for TSLA',
    ],
  },
  {
    label: 'Compliance',
    queries: [
      'Is NVDA on the restricted list',
      'Can I trade AAPL',
      'Compliance screen TSLA',
      'Check trading restrictions on MSFT',
    ],
  },
  {
    label: 'Watchlist',
    queries: [
      'Show my watchlist',
      'What tickers am I following',
    ],
  },
  {
    label: 'Multi-turn / Misc',
    queries: [
      'Hello',
      'What can you do',
      'Tell me about NVDA',
      'What about its coverage',
      'How does it compare to AAPL',
    ],
  },
];

interface Props {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export default function SampleQueries({ onSelect, disabled }: Props) {
  // Top-level collapse (entire panel). Start collapsed to save space.
  const [panelOpen, setPanelOpen] = useState(false);
  // Per-category collapse within the panel; first 3 expanded by default
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  const toggle = (idx: number) =>
    setCollapsed((prev) => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div
      className="slds-p-horizontal_small slds-p-bottom_x-small"
      role="region"
      aria-label="Sample queries"
    >
      <button
        onClick={() => setPanelOpen((o) => !o)}
        aria-expanded={panelOpen}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          width: '100%',
          textAlign: 'left',
          fontSize: '0.75rem',
          color: '#706e6b',
          marginBottom: panelOpen ? '6px' : 0,
        }}
      >
        <span>{panelOpen ? '▾' : '▸'}</span>
        <span>Try a sample query</span>
      </button>
      {panelOpen && (
        <>
          {SAMPLE_CATEGORIES.map((cat, idx) => {
            const isCollapsed = collapsed[idx] ?? idx > 2;
            return (
              <div key={cat.label} className="slds-m-bottom_xx-small">
                <button
                  onClick={() => toggle(idx)}
                  aria-expanded={!isCollapsed}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: '#3e3e3c',
                    marginBottom: '2px',
                  }}
                >
                  {cat.label} {isCollapsed ? '▸' : '▾'}
                </button>
                {!isCollapsed && (
                  <div>
                    {cat.queries.map((q) => (
                      <button
                        key={q}
                        className="slds-button slds-button_outline-brand slds-button_small"
                        onClick={() => onSelect(q)}
                        disabled={disabled}
                        aria-label={`Ask: ${q}`}
                        style={{
                          borderRadius: '1rem',
                          fontSize: '0.75rem',
                          margin: '0 4px 4px 0',
                        }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

/**
 * Categorized, collapsible sample queries for the 006 FSI Research Agent.
 *
 * Categories reflect the MCP tools + pipeline capabilities:
 * Market Data, SEC Filings, News, CRM, Valuation, Compliance, Pipeline.
 * Queries span 15 tickers across sectors so the tester sees variety.
 *
 * Pattern: top-level panel toggle (starts collapsed), first 3 categories
 * expanded by default, rest collapsed — click heading to toggle.
 */

import { useState } from 'react';

const SAMPLE_CATEGORIES = [
  {
    label: 'Company Lookup',
    queries: [
      'Tell me about NVDA',
      'Look up AAPL',
      'What is JPMorgan Chase',
      'Describe Eli Lilly',
      'Tell me about PLTR',
      'What does CrowdStrike do',
    ],
  },
  {
    label: 'Market Data',
    queries: [
      "What's NVIDIA trading at?",
      'Current price of AAPL',
      'TSLA 52-week high and low',
      'MSFT price history for 30 days',
      'AMZN market cap',
      'JPM dividend yield',
      'Show me options chain for GOOGL',
    ],
  },
  {
    label: 'Analyst Coverage',
    queries: [
      'Who covers NVDA on our team?',
      'Analyst ratings for AAPL',
      'Show me coverage for TSLA',
      "What's our current rating on META?",
      'Consensus target price for MSFT',
      'Coverage details for LLY',
    ],
  },
  {
    label: 'SEC Filings',
    queries: [
      'NVDA latest 10-K filing',
      "Summarize risk factors from Apple's latest 10-K",
      'Microsoft 8-K filings',
      'Tesla recent SEC filings',
      'GOOGL 10-Q highlights',
      'Insider transactions for NVDA',
    ],
  },
  {
    label: 'News & Sentiment',
    queries: [
      'Latest news on NVDA',
      'Headlines for Apple',
      "What's the sentiment on Tesla",
      'Recent news about META',
      'Is GOOGL bullish or bearish right now',
      'Any news on Eli Lilly GLP-1',
    ],
  },
  {
    label: 'Valuation & Analysis',
    queries: [
      'DCF valuation for NVDA',
      'Fair value estimate for AAPL',
      'Monte Carlo simulation on GOOGL',
      'Comps-based valuation for MSFT',
      'Is TSLA overvalued or undervalued',
      'Side-by-side: AAPL vs MSFT vs GOOGL — P/E, revenue growth, margins',
    ],
  },
  {
    label: 'Compliance & MNPI',
    queries: [
      'Is NVDA on the restricted list',
      'Can I trade AAPL right now',
      'Compliance screen for TSLA',
      'Check trading restrictions on MSFT',
      "We're about to publish a rating change on NVDA. Which employees hold it?",
    ],
  },
  {
    label: 'Research Pipeline',
    queries: [
      'Deep dive on NVIDIA ahead of earnings',
      'Research note on Costco — same-store sales, membership economics',
      'Full research brief on JPM',
      'Initiate coverage on PLTR',
      'Earnings preview for LLY',
    ],
  },
  {
    label: 'CRM & Watchlist',
    queries: [
      'Show my watchlist',
      'What tickers am I following',
      'Any prior research notes on NVDA',
      'Who is the primary analyst for AAPL',
    ],
  },
  {
    label: 'Edge Cases & Multi-turn',
    queries: [
      'Hello',
      'What can you do',
      "I heard from NVIDIA's CFO that they're going to miss earnings. Should I sell?",
      'Compare NVDA and AMD',
      'Tell me about NVDA — then show me its filings',
    ],
  },
];

interface Props {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export default function SampleQueries({ onSelect, disabled }: Props) {
  const [panelOpen, setPanelOpen] = useState(false);
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
        className={`slds-button slds-text-body_small slds-text-color_weak slds-grid slds-grid_vertical-align-center${panelOpen ? ' slds-m-bottom_xx-small' : ''}`}
        onClick={() => setPanelOpen((o) => !o)}
        aria-expanded={panelOpen}
      >
        <span className="slds-m-right_xx-small">{panelOpen ? '▾' : '▸'}</span>
        <span>Try a sample query</span>
      </button>
      {panelOpen && (
        <>
          {SAMPLE_CATEGORIES.map((cat, idx) => {
            const isCollapsed = collapsed[idx] ?? idx > 2;
            return (
              <div key={cat.label} className="slds-m-bottom_xx-small">
                <button
                  className="slds-button slds-text-body_small slds-text-title_caps slds-m-bottom_xx-small"
                  onClick={() => toggle(idx)}
                  aria-expanded={!isCollapsed}
                >
                  {cat.label} {isCollapsed ? '▸' : '▾'}
                </button>
                {!isCollapsed && (
                  <div>
                    {cat.queries.map((q) => (
                      <button
                        key={q}
                        className="slds-button slds-button_outline-brand slds-button_small slds-m-right_xx-small slds-m-bottom_xx-small"
                        onClick={() => onSelect(q)}
                        disabled={disabled}
                        aria-label={`Ask: ${q}`}
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

/**
 * Categorized sample query pills for the wealth advisor agent.
 * Each category has a label header and pill buttons below it.
 */

import { useState } from 'react';

const SAMPLE_CATEGORIES = [
  {
    label: '👤 Client Lookup',
    queries: ['Tell me about the Johnsons', 'Who is Wei Chen?', 'Look up the Patel family'],
  },
  {
    label: '📊 Portfolio',
    queries: ["How is Wei Chen's portfolio?", "Show me Johnson's allocation", 'Patel portfolio review'],
  },
  {
    label: '🎯 Goals',
    queries: ["What are the Patels' goals?", 'Johnson retirement progress', 'Chen college fund status'],
  },
  {
    label: '📋 Meeting Prep',
    queries: ['Prep me for my meeting with Carlos', 'Meeting brief for Raj Patel'],
  },
  {
    label: '⚖️ Rebalancing',
    queries: ['Does Sarah Johnson need rebalancing?', 'Check drift for Chen family'],
  },
  {
    label: '💳 Transactions',
    queries: ['Show me recent transactions for Wei Chen', 'Johnson transaction history'],
  },
  {
    label: '✅ Compliance',
    queries: ['Is the Patel account compliant?', 'Run compliance check on Martinez'],
  },
  {
    label: '🤝 Referrals',
    queries: ['Who referred the Williams family?', 'Referral status for Chen'],
  },
];

interface Props {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export default function SampleQueries({ onSelect, disabled }: Props) {
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  const toggle = (idx: number) => {
    setCollapsed((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="slds-p-horizontal_small slds-p-bottom_x-small" role="region" aria-label="Sample queries">
      <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_xx-small">
        Try a sample query:
      </p>
      {SAMPLE_CATEGORIES.map((cat, idx) => {
        const isCollapsed = collapsed[idx] ?? false;
        return (
          <div key={cat.label} className="slds-m-bottom_xx-small">
            <button
              className="wa-category-label"
              onClick={() => toggle(idx)}
              aria-expanded={!isCollapsed}
              aria-controls={`wa-cat-${idx}`}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                display: 'block',
                width: '100%',
                textAlign: 'left',
              }}
            >
              {cat.label} {isCollapsed ? '▸' : '▾'}
            </button>
            {!isCollapsed && (
              <div id={`wa-cat-${idx}`} className="wa-category-queries">
                {cat.queries.map((q) => (
                  <button
                    key={q}
                    className="slds-button slds-button_outline-brand slds-button_small"
                    onClick={() => onSelect(q)}
                    disabled={disabled}
                    aria-label={`Ask: ${q}`}
                    style={{ borderRadius: '1rem', fontSize: '0.75rem', margin: '0 4px 4px 0' }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

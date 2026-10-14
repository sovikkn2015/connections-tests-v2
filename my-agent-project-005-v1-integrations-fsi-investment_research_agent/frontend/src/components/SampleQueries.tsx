/**
 * Quick-action pill buttons for sample queries.
 * Uses SLDS pill/button styling.
 */

const SAMPLES = [
  'Tell me about NVIDIA',
  'Who covers NVDA?',
  'NVDA fair value',
  'Show me NVDA 10-K',
  'Can I trade NVDA?',
  "What's on my watchlist?",
];

interface Props {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export default function SampleQueries({ onSelect, disabled }: Props) {
  return (
    <div className="slds-p-horizontal_small slds-p-bottom_x-small">
      <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_xx-small">
        Try a sample query:
      </p>
      <div className="slds-grid slds-wrap slds-gutters_xx-small">
        {SAMPLES.map((q) => (
          <div key={q} className="slds-m-bottom_xx-small slds-m-right_xx-small">
            <button
              className="slds-button slds-button_outline-brand slds-button_small"
              onClick={() => onSelect(q)}
              disabled={disabled}
              aria-label={`Ask: ${q}`}
              style={{ borderRadius: '1rem', fontSize: '0.75rem' }}
            >
              {q}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

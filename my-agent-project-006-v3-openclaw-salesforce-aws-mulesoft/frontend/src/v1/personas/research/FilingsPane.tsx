/**
 * Right-rail data pane — filings retrieval status. Shows which sections were
 * retrieved and offers quick drill-down into any citation.
 */

import { useBriefStore } from '../../../shared/store/brief';

export function FilingsPane({ onOpenCitation }: { onOpenCitation?: (id: string) => void }) {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const filings = Object.values(citations).filter((c) => c.source_type === 'filing');

  return (
    <section className="research-pane" aria-label="Filings">
      <header className="research-pane__header">
        <span>Filings</span>
        <span>{filings.length} cited</span>
      </header>
      <div className="research-pane__body">
        {filings.length === 0 && <div style={{ opacity: 0.7 }}>no filings cited yet</div>}
        {filings.map((c) => (
          <div
            key={c.span_id}
            style={{
              padding: '0.375rem 0',
              borderBottom: '1px solid #1C2B3F',
              cursor: 'pointer',
            }}
            onClick={() => onOpenCitation?.(c.source_id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onOpenCitation?.(c.source_id);
            }}
          >
            <div style={{ fontWeight: 600 }}>{c.label}</div>
            {c.page && (
              <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                p. {c.page}
                {c.paragraph && ` · ¶${c.paragraph}`}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

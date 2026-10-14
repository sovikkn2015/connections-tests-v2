/**
 * Right column — MNPI-filtered client context. Positions rendered as
 * percentages / concentration bands, not absolute dollars (narrative §1
 * portfolio specialist handling: "work in percentages and bands").
 */

import { useQueuesStore } from '../../../shared/store/queues';

export function ClientContextPanel() {
  const selectedId = useQueuesStore((s) => s.selectedItemId);
  const items = useQueuesStore((s) => s.itemsByQueue);
  const selected = selectedId
    ? Object.values(items)
        .flat()
        .find((it) => it.id === selectedId)
    : null;

  return (
    <div className="advisor-column">
      <div className="advisor-column__header">Client context</div>
      <div className="advisor-column__body advisor-client-context">
        {!selected && (
          <div style={{ padding: '0.75rem', color: '#706E6B' }}>Select an item to see context</div>
        )}
        {selected && (
          <>
            <div className="advisor-client-context__row">
              <span>Household</span>
              <strong>{selected.client_contact_id ?? '—'}</strong>
            </div>
            {selected.brief_id && (
              <div className="advisor-client-context__row">
                <span>Based on brief</span>
                <strong>{selected.brief_id}</strong>
              </div>
            )}
            <div
              style={{
                marginTop: '0.75rem',
                fontSize: '0.75rem',
                color: '#706E6B',
                borderTop: '1px solid var(--v3-border)',
                paddingTop: '0.5rem',
              }}
            >
              Positions expressed as % concentration. MNPI-filtered by the trust layer — raw share
              counts never reach this view.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

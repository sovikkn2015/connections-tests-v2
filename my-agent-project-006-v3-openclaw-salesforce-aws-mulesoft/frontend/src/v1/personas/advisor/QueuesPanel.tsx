/**
 * RM's left panel — 4 queue tabs + items list. Tabs light up with per-queue
 * counts; clicking an item selects it for the conversation panel.
 */

import { useState } from 'react';
import { QueueItem } from '../../components/QueueItem';
import { useQueuesStore } from '../../../shared/store/queues';
import type { AdvisorQueueKind } from '../../../shared/types/api';

const TABS: Array<{ kind: AdvisorQueueKind; label: string }> = [
  { kind: 'inbox', label: 'Inbox' },
  { kind: 'briefs', label: 'Briefs' },
  { kind: 'alerts', label: 'Alerts' },
  { kind: 'pending', label: 'Pending' },
];

export function QueuesPanel() {
  const [active, setActive] = useState<AdvisorQueueKind>('inbox');
  const itemsByQueue = useQueuesStore((s) => s.itemsByQueue);
  const items = itemsByQueue[active];
  const selectedId = useQueuesStore((s) => s.selectedItemId);
  const selectItem = useQueuesStore((s) => s.selectItem);

  return (
    <div className="advisor-column">
      <div className="advisor-column__header">Queues</div>
      <div role="tablist" aria-label="Advisor queues">
        {TABS.map((t) => {
          const count = itemsByQueue[t.kind].length;
          return (
            <div
              key={t.kind}
              role="tab"
              aria-selected={active === t.kind}
              className="advisor-queue-tab"
              onClick={() => setActive(t.kind)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setActive(t.kind);
              }}
            >
              {t.label}
              {count > 0 && <span className="advisor-queue-tab__badge">{count}</span>}
            </div>
          );
        })}
      </div>
      <div className="advisor-column__body" role="tabpanel">
        {items.length === 0 && (
          <div style={{ padding: '0.75rem', color: '#706E6B', fontSize: '0.8125rem' }}>
            No items
          </div>
        )}
        {items.map((it) => (
          <QueueItem
            key={it.id}
            item={it}
            selected={it.id === selectedId}
            onSelect={selectItem}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Sarah's "Client demand signals" tab — pre-seeded rows representing inquiries
 * surfaced to research. Accept = queue a research brief for that subject.
 */

import { QueueItem } from '../../components/QueueItem';
import type { QueueItemSummary } from '../../../shared/types/api';

export interface DemandSignalsTabProps {
  items: QueueItemSummary[];
  onAccept: (id: string) => void;
}

export function DemandSignalsTab({ items, onAccept }: DemandSignalsTabProps) {
  return (
    <section className="research-pane" aria-label="Client demand signals">
      <header className="research-pane__header">
        <span>Client Demand Signals</span>
        <span>{items.length}</span>
      </header>
      <div className="research-pane__body">
        {items.length === 0 && <div style={{ opacity: 0.7 }}>no signals</div>}
        {items.map((it) => (
          <div key={it.id} className="research-demand-signals__row">
            <QueueItem item={it} onSelect={onAccept} />
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * Reusable queue row. Used by the RM's four queues and by Sarah's demand
 * signals tab. Keyboard-navigable; `data-unread` highlights fresh items.
 */

import type { KeyboardEvent } from 'react';
import { cx } from '../../shared/lib/slds';
import type { QueueItemSummary } from '../../shared/types/api';

export interface QueueItemProps {
  item: QueueItemSummary;
  selected?: boolean;
  onSelect?: (id: string) => void;
}

export function QueueItem({ item, selected, onSelect }: QueueItemProps) {
  const handleClick = () => onSelect?.(item.id);
  const handleKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect?.(item.id);
    }
  };

  return (
    <div
      className={cx('advisor-queue-item', selected && 'advisor-queue-item--selected')}
      data-unread={item.unread ? 'true' : 'false'}
      data-testid={`queue-item-${item.id}`}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKey}
      aria-pressed={selected}
    >
      <div className="advisor-queue-item__title">
        {item.title}
        {item.badge && (
          <span
            style={{
              marginLeft: '0.375rem',
              fontSize: '0.6875rem',
              padding: '0.0625rem 0.375rem',
              background: '#E5F1FB',
              color: '#0176D3',
              borderRadius: '0.25rem',
            }}
          >
            {item.badge}
          </span>
        )}
      </div>
      {item.subtitle && <div className="advisor-queue-item__subtitle">{item.subtitle}</div>}
      <div className="advisor-queue-item__meta">
        <span>{item.kind}</span>
        <time dateTime={item.timestamp}>
          {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </time>
      </div>
    </div>
  );
}

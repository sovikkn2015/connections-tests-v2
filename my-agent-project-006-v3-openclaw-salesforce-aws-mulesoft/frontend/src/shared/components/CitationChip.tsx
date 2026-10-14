/**
 * Clickable citation chip. Hover -> source metadata tooltip (title attr).
 * Click -> calls onOpen(source_id) which loads the source chunk in a side pane.
 *
 * If the citation channel hasn't delivered metadata yet, the chip renders in
 * a "pending" state (deterministic fallback — narrative §6).
 */

import type { KeyboardEvent } from 'react';
import type { Citation } from '../types/api';

export interface CitationChipProps {
  spanId: string;
  citation: Citation | undefined;
  onOpen?: (sourceId: string) => void;
}

export function CitationChip({ spanId, citation, onOpen }: CitationChipProps) {
  const pending = !citation;
  const label = citation?.label ?? 'citation…';
  const title = citation
    ? `${citation.source_type}: ${citation.label}${citation.page ? ` (p.${citation.page})` : ''}`
    : 'Citation loading…';

  const handleClick = () => {
    if (!citation || !onOpen) return;
    onOpen(citation.source_id);
  };

  const handleKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <span
      className="v3-chip"
      data-pending={pending ? 'true' : 'false'}
      data-testid={`chip-${spanId}`}
      role={pending ? 'status' : 'button'}
      tabIndex={pending ? -1 : 0}
      title={title}
      aria-label={title}
      onClick={handleClick}
      onKeyDown={handleKey}
    >
      {label}
    </span>
  );
}

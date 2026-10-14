/**
 * Markdown streaming with citation stitch.
 *
 * Uses splitMarkdown to tokenize the Markdown, then renders each text run and
 * each citation marker. Citation metadata flows separately over the WebSocket;
 * if a chip's metadata hasn't arrived yet, it renders pending.
 *
 * No real Markdown parser — the brief is rendered as plain text with citation
 * chips inline. Cheaper, more predictable, and matches the narrative choice
 * that "the content is prose, not a document."
 */

import { Fragment } from 'react';
import { splitMarkdown } from '../lib/citationParser';
import { CitationChip } from './CitationChip';
import type { Citation } from '../types/api';

export interface StreamingTextProps {
  markdown: string;
  citations: Record<string, Citation>;
  onOpenCitation?: (sourceId: string) => void;
  isStreaming?: boolean;
}

export function StreamingText({
  markdown,
  citations,
  onOpenCitation,
  isStreaming,
}: StreamingTextProps) {
  const tokens = splitMarkdown(markdown);
  return (
    <div aria-live="polite" aria-atomic="false">
      {tokens.map((tok, i) => {
        if (tok.kind === 'text') {
          return <Fragment key={i}>{tok.value}</Fragment>;
        }
        return (
          <CitationChip
            key={`chip-${tok.span_id}-${i}`}
            spanId={tok.span_id}
            citation={citations[tok.span_id]}
            onOpen={onOpenCitation}
          />
        );
      })}
      {isStreaming && (
        <span className="v3-streaming-cursor" aria-hidden="true">
          ▊
        </span>
      )}
    </div>
  );
}

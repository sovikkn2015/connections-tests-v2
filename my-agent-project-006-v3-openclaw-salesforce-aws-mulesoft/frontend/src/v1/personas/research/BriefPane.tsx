/**
 * Center pane on Sarah's terminal — the streaming brief with citation chips
 * and any embedded charts the model emitted (chart_intent events).
 */

import { useBriefStore } from '../../../shared/store/brief';
import { StreamingText } from '../../../shared/components/StreamingText';
import { DeterministicChart } from '../../components/DeterministicChart';
import { SkeletonTool } from '../../../shared/components/SkeletonTool';
import type { SourceTable } from '../../../shared/types/api';

export interface BriefPaneProps {
  loadSourceTable: (id: string) => Promise<SourceTable>;
  onOpenCitation?: (sourceId: string) => void;
}

export function BriefPane({ loadSourceTable, onOpenCitation }: BriefPaneProps) {
  const markdown = useBriefStore((s) => s.markdown);
  const citations = useBriefStore((s) => s.citationsBySpan);
  const charts = useBriefStore((s) => s.charts);
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const isStreaming = useBriefStore((s) => s.isStreaming);
  const running = toolCalls.filter((t) => t.status === 'running');

  return (
    <section className="research-pane" aria-label="Brief">
      <header className="research-pane__header">
        <span>Brief — citation-enforced</span>
        {isStreaming && <span style={{ color: '#1B96FF' }}>streaming…</span>}
      </header>
      <div className="research-pane__body">
        {running.length > 0 && (
          <div
            style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginBottom: '0.5rem' }}
          >
            {running.map((t) => (
              <SkeletonTool key={t.span_id} tool={t} />
            ))}
          </div>
        )}
        <div className="research-brief">
          <StreamingText
            markdown={markdown}
            citations={citations}
            onOpenCitation={onOpenCitation}
            isStreaming={isStreaming}
          />
        </div>
        {charts.map((chart, i) => (
          <div key={i} style={{ marginTop: '1rem' }}>
            <DeterministicChart
              intent={chart}
              loader={loadSourceTable}
              onOpenCitation={onOpenCitation}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

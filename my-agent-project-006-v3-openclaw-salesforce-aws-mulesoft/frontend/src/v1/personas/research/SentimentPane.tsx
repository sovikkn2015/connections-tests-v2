/**
 * Right-rail data pane — 30-day sentiment score summary from the sentiment
 * specialist. We display the citation count from news sources.
 */

import { useBriefStore } from '../../../shared/store/brief';

export function SentimentPane() {
  const citations = useBriefStore((s) => s.citationsBySpan);
  const toolCalls = useBriefStore((s) => s.toolCalls);
  const news = Object.values(citations).filter((c) => c.source_type === 'news');
  const latest = [...toolCalls].reverse().find((t) => t.tool_name === 'news-search');

  return (
    <section className="research-pane" aria-label="Sentiment">
      <header className="research-pane__header">
        <span>Sentiment — 30d</span>
        <span>{latest?.status ?? 'idle'}</span>
      </header>
      <div className="research-pane__body">
        <div>
          news citations: <strong>{news.length}</strong>
        </div>
        {latest?.status === 'running' && <div className="v3-skeleton">news-search…</div>}
        {latest?.status === 'error' && (
          <div role="alert" style={{ color: '#F47067' }}>
            sentiment lookup failed — brief marked "limited data"
          </div>
        )}
      </div>
    </section>
  );
}

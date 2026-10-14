/**
 * SampleQueries — collapsible panel of categorised sample queries.
 *
 * Renders a `<details>` element (starts closed) with categorised query
 * buttons. Clicking a query calls `onSelect(text)` which the parent
 * wires to populate-and-submit.
 *
 * Narrative-arc queries are badged so the demo operator can follow the
 * scripted story without hunting.
 */

export interface SampleQuery {
  text: string;
  /** If true, this query is part of the demo narrative arc */
  narrative?: boolean;
  /** Short explanation of what this query demonstrates */
  hint?: string;
}

export interface QueryCategory {
  label: string;
  queries: SampleQuery[];
}

export interface SampleQueriesProps {
  categories: QueryCategory[];
  onSelect: (text: string) => void;
}

export function SampleQueries({ categories, onSelect }: SampleQueriesProps) {
  const totalCount = categories.reduce((n, c) => n + c.queries.length, 0);

  return (
    <div className="v6-samples">
      <details>
        <summary>
          Sample queries
          <span className="v6-samples__count">{totalCount}</span>
        </summary>
        <div className="v6-samples__body">
          {categories.map((cat) => (
            <details key={cat.label} className="v6-samples__cat-details">
              <summary className="v6-samples__category">
                {cat.label}
                <span className="v6-samples__cat-count">{cat.queries.length}</span>
              </summary>
              <div className="v6-samples__cat-body">
                {cat.queries.map((q) => (
                  <button
                    key={q.text}
                    type="button"
                    className="v6-samples__item"
                    onClick={() => onSelect(q.text)}
                  >
                    <div className="v6-samples__item-text">
                      {q.text}
                      {q.narrative && <span className="v6-samples__narrative">🎯 narrative</span>}
                    </div>
                    {q.hint && <div className="v6-samples__hint">{q.hint}</div>}
                  </button>
                ))}
              </div>
            </details>
          ))}
        </div>
      </details>
    </div>
  );
}

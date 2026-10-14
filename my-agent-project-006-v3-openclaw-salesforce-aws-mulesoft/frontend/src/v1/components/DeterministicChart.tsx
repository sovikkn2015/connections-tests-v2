/**
 * LLM-intent -> Visx render.
 *
 * Loads the parsed source table via loader. Visx Bar / Line render from the
 * numeric table, NOT from the LLM. Hover = citation, click bar = drill.
 * If table fetch fails, we render the tabular fallback (narrative §6).
 */

import { useEffect, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { LinePath } from '@visx/shape';
import { AxisBottom, AxisLeft } from '@visx/axis';
import { Group } from '@visx/group';
import { scaleBand, scaleLinear } from '@visx/scale';
import type { ChartIntent, SourceTable } from '../../shared/types/api';
import { buildChartSpec, fallbackTable, type ChartSpec } from '../../shared/lib/chartRenderer';
import { SLDS } from '../../shared/lib/slds';

export interface DeterministicChartProps {
  intent: ChartIntent;
  loader: (sourceId: string) => Promise<SourceTable>;
  onOpenCitation?: (sourceId: string) => void;
  onDrillSegment?: (segmentKey: string) => void;
  width?: number;
  height?: number;
}

export function DeterministicChart({
  intent,
  loader,
  onOpenCitation,
  onDrillSegment,
  width = 480,
  height = 240,
}: DeterministicChartProps) {
  const [table, setTable] = useState<SourceTable | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loader(intent.source_id)
      .then((t) => {
        if (!cancelled) setTable(t);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [intent.source_id, loader]);

  if (error) {
    return (
      <div role="alert" className="slds-box slds-theme_warning">
        Unable to load source table — {error}
      </div>
    );
  }

  if (!table) {
    return (
      <div className="v3-skeleton" data-testid="chart-loading">
        loading {intent.source_id}…
      </div>
    );
  }

  const spec = buildChartSpec(intent, table);
  if (spec.data.length === 0) {
    return <FallbackTable spec={spec} />;
  }

  return (
    <figure data-testid={`chart-${intent.source_id}`}>
      <figcaption>
        <strong>{spec.title}</strong>{' '}
        <button
          type="button"
          className="v3-chip"
          onClick={() => onOpenCitation?.(spec.citation.source_id)}
          aria-label={`Open source ${spec.citation.label}`}
        >
          {spec.citation.label}
        </button>
      </figcaption>
      {spec.kind === 'bar' ? (
        <BarChart spec={spec} width={width} height={height} onDrill={onDrillSegment} />
      ) : spec.kind === 'line' ? (
        <LineChart spec={spec} width={width} height={height} />
      ) : (
        <FallbackTable spec={spec} />
      )}
    </figure>
  );
}

function BarChart({
  spec,
  width,
  height,
  onDrill,
}: {
  spec: ChartSpec;
  width: number;
  height: number;
  onDrill?: (key: string) => void;
}) {
  const margin = { top: 16, right: 16, bottom: 32, left: 48 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xScale = scaleBand<string>({
    domain: spec.data.map((p) => p.label),
    range: [0, innerW],
    padding: 0.2,
  });
  const maxV = Math.max(...spec.data.map((p) => p.value), 0);
  const yScale = scaleLinear<number>({ domain: [0, maxV || 1], range: [innerH, 0] });

  const handleKey = (e: KeyboardEvent, key: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onDrill?.(key);
    }
  };

  return (
    <svg width={width} height={height} role="img" aria-label={spec.title}>
      <Group top={margin.top} left={margin.left}>
        {spec.data.map((p) => {
          const x = xScale(p.label) ?? 0;
          const barW = xScale.bandwidth();
          const barH = innerH - yScale(p.value);
          return (
            <rect
              key={p.key}
              x={x}
              y={yScale(p.value)}
              width={barW}
              height={barH}
              fill={p.highlighted ? SLDS.brandLight : SLDS.brandAccessibleActive}
              role="button"
              aria-label={`${p.label} ${p.value}`}
              tabIndex={0}
              onClick={() => onDrill?.(p.key)}
              onKeyDown={(e) => handleKey(e, p.key)}
              style={{ cursor: onDrill ? 'pointer' : 'default' }}
            />
          );
        })}
        <AxisBottom top={innerH} scale={xScale} />
        <AxisLeft scale={yScale} numTicks={5} />
      </Group>
    </svg>
  );
}

function LineChart({ spec, width, height }: { spec: ChartSpec; width: number; height: number }) {
  const margin = { top: 16, right: 16, bottom: 32, left: 48 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xScale = scaleLinear<number>({
    domain: [0, Math.max(spec.data.length - 1, 1)],
    range: [0, innerW],
  });
  const maxV = Math.max(...spec.data.map((p) => p.value), 0);
  const yScale = scaleLinear<number>({ domain: [0, maxV || 1], range: [innerH, 0] });

  return (
    <svg width={width} height={height} role="img" aria-label={spec.title}>
      <Group top={margin.top} left={margin.left}>
        <LinePath
          data={spec.data}
          x={(_, i) => xScale(i) ?? 0}
          y={(d) => yScale(d.value) ?? 0}
          stroke={SLDS.brandAccessibleActive}
          strokeWidth={2}
        />
        <AxisBottom top={innerH} scale={xScale} numTicks={Math.min(spec.data.length, 8)} />
        <AxisLeft scale={yScale} numTicks={5} />
      </Group>
    </svg>
  );
}

function FallbackTable({ spec }: { spec: ChartSpec }) {
  const rows = fallbackTable(spec);
  return (
    <table
      className="slds-table slds-table_cell-buffer slds-table_bordered"
      aria-label={`${spec.title} — tabular fallback`}
    >
      <caption className="slds-assistive-text">Tabular fallback</caption>
      <thead>
        <tr>
          <th scope="col">{spec.xLabel}</th>
          <th scope="col">{spec.yLabel}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, value], i) => (
          <tr key={i}>
            <td>{label}</td>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

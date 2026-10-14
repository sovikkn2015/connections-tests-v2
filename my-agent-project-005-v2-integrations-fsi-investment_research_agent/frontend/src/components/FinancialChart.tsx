/**
 * Enhanced Financial Analysis Suite.
 * Metric-toggle chart, fair-value card, Monte Carlo range, and peer comps table.
 */

import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Area,
} from 'recharts';
import { useAgentStore } from '../store/agentStore';
import { formatPrice, formatPct } from '../services/responseParser';
import type { ChartMetric } from '../types';

/* ── Metric button labels ── */
const METRICS: { key: ChartMetric; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'margins', label: 'Margins' },
  { key: 'eps', label: 'EPS' },
  { key: 'fcf', label: 'FCF' },
];

/* ── Y-axis label per metric ── */
const Y_LABELS: Record<ChartMetric, string> = {
  revenue: 'Revenue ($B)',
  margins: 'Margin (%)',
  eps: 'EPS ($)',
  fcf: 'FCF ($B)',
};

export default function FinancialChart() {
  const {
    chartData,
    chartMetric,
    setChartMetric,
    valuationData,
  } = useAgentStore();

  const hasChart = chartData && chartData.length > 0;
  const hasValuation = !!valuationData;

  /* ── Empty state ── */
  if (!hasChart && !hasValuation) {
    return (
      <div className="slds-p-around_large slds-text-align_center">
        <p className="slds-text-body_regular slds-text-color_weak">
          Ask for a fair value analysis to see financial charts.
        </p>
      </div>
    );
  }


  /* ── Render chart series based on selected metric ── */
  const renderSeries = () => {
    switch (chartMetric) {
      case 'revenue':
        return (
          <Bar
            yAxisId="left"
            dataKey="revenue"
            name="Revenue ($B)"
            fill="#0070d2"
            radius={[2, 2, 0, 0]}
          />
        );
      case 'margins':
        return (
          <>
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="grossMargin"
              name="Gross Margin (%)"
              stroke="#04844b"
              fill="#04844b20"
              strokeWidth={2}
            />
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="operatingMargin"
              name="Op. Margin (%)"
              stroke="#0070d2"
              fill="#0070d220"
              strokeWidth={2}
            />
          </>
        );
      case 'eps':
        return (
          <Bar
            yAxisId="left"
            dataKey="eps"
            name="EPS ($)"
            fill="#ff9e2c"
            radius={[2, 2, 0, 0]}
          />
        );
      case 'fcf':
        return (
          <Bar
            yAxisId="left"
            dataKey="fcf"
            name="FCF ($B)"
            fill="#1b96ff"
            radius={[2, 2, 0, 0]}
          />
        );
    }
  };

  /* ── Peer averages ── */
  const peers = valuationData?.peers ?? [];
  const peerAvg = peers.length
    ? {
        peRatio: peers.reduce((s, p) => s + p.peRatio, 0) / peers.length,
        evEbitda: peers.reduce((s, p) => s + p.evEbitda, 0) / peers.length,
        psRatio: peers.reduce((s, p) => s + p.psRatio, 0) / peers.length,
        currentPrice: peers.reduce((s, p) => s + p.currentPrice, 0) / peers.length,
      }
    : null;

  return (
    <div className="slds-p-around_small">
      {/* ── 1. Chart Type Toggle ── */}
      {hasChart && (
        <div
          className="slds-button-group slds-m-bottom_small"
          role="group"
          aria-label="Chart metric selector"
        >
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`slds-button ${
                chartMetric === m.key
                  ? 'slds-button_brand'
                  : 'slds-button_neutral'
              }`}
              aria-pressed={chartMetric === m.key}
              onClick={() => setChartMetric(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}


      {/* ── 2. Recharts Chart ── */}
      {hasChart && (
        <article className="slds-card slds-m-bottom_small">
          <div className="slds-card__header">
            <h2 className="slds-card__header-title slds-text-heading_small">
              Financial Overview
            </h2>
          </div>
          <div className="slds-card__body slds-card__body_inner">
            <div style={{ width: '100%', height: 280 }} role="img" aria-label={`${Y_LABELS[chartMetric]} chart`}>
              <ResponsiveContainer>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d8dde6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#706e6b' }} />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11, fill: '#706e6b' }}
                    label={{
                      value: Y_LABELS[chartMetric],
                      angle: -90,
                      position: 'insideLeft',
                      style: { fontSize: 11, fill: '#706e6b' },
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#ffffff',
                      border: '1px solid #d8dde6',
                      borderRadius: '0.25rem',
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {renderSeries()}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </article>
      )}


      {/* ── 3. Fair Value Summary Card ── */}
      {hasValuation && (
        <article className="slds-card slds-m-bottom_small" aria-label="Fair value summary">
          <div className="slds-card__header">
            <h2 className="slds-card__header-title slds-text-heading_small">
              Fair Value Summary
            </h2>
          </div>
          <div className="slds-card__body slds-card__body_inner">
            <div className="slds-grid slds-gutters_small slds-wrap">
              <div className="slds-col slds-size_1-of-3 slds-text-align_center">
                <p className="slds-text-title slds-m-bottom_xx-small">DCF Fair Value</p>
                <p className="slds-text-heading_medium">${formatPrice(valuationData.dcfFairValue)}</p>
              </div>
              <div className="slds-col slds-size_1-of-3 slds-text-align_center">
                <p className="slds-text-title slds-m-bottom_xx-small">Current Price</p>
                <p className="slds-text-heading_medium">${formatPrice(valuationData.currentPrice)}</p>
              </div>
              <div className="slds-col slds-size_1-of-3 slds-text-align_center">
                <p className="slds-text-title slds-m-bottom_xx-small">Upside/Downside</p>
                <p
                  className="slds-text-heading_medium"
                  style={{ color: valuationData.upsidePct >= 0 ? '#04844b' : '#c23934' }}
                >
                  {formatPct(valuationData.upsidePct)}
                </p>
              </div>
            </div>
          </div>
        </article>
      )}


      {/* ── 4. Monte Carlo Range Bar ── */}
      {hasValuation && (
        <div className="ir-mc-range slds-m-bottom_small slds-p-around_small" aria-label="Monte Carlo simulation range">
          <p className="slds-text-title slds-m-bottom_xx-small">
            Monte Carlo 1yr (500 sims)
          </p>
          <div
            className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center"
            style={{ position: 'relative', height: 32 }}
          >
            <span className="slds-text-body_small">${formatPrice(valuationData.monteCarloP5)}</span>
            <div
              style={{
                flex: 1,
                height: 8,
                margin: '0 0.75rem',
                background: 'linear-gradient(90deg, #c23934, #f4f6f9 50%, #04844b)',
                borderRadius: 4,
                position: 'relative',
              }}
              role="meter"
              aria-valuenow={valuationData.monteCarloMedian}
              aria-valuemin={valuationData.monteCarloP5}
              aria-valuemax={valuationData.monteCarloP95}
              aria-label="Monte Carlo median price"
            >
              {/* Median dot */}
              <div
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: `${
                    ((valuationData.monteCarloMedian - valuationData.monteCarloP5) /
                      (valuationData.monteCarloP95 - valuationData.monteCarloP5)) *
                    100
                  }%`,
                  transform: 'translate(-50%, -50%)',
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: '#0070d2',
                  border: '2px solid #ffffff',
                  boxShadow: '0 0 3px rgba(0,0,0,0.3)',
                }}
                title={`Median: $${formatPrice(valuationData.monteCarloMedian)}`}
              />
            </div>
            <span className="slds-text-body_small">${formatPrice(valuationData.monteCarloP95)}</span>
          </div>
        </div>
      )}


      {/* ── 5. Peer Comparison Table ── */}
      {peers.length > 0 && (
        <article className="slds-card" aria-label="Peer comparison">
          <div className="slds-card__header">
            <h2 className="slds-card__header-title slds-text-heading_small">
              Peer Comparison
            </h2>
          </div>
          <div className="slds-card__body">
            <table className="slds-table slds-table_cell-buffer slds-table_bordered" aria-label="Peer comparison data">
              <thead>
                <tr className="slds-line-height_reset">
                  <th scope="col"><div className="slds-truncate" title="Ticker">Ticker</div></th>
                  <th scope="col"><div className="slds-truncate" title="Name">Name</div></th>
                  <th scope="col"><div className="slds-truncate" title="P/E">P/E</div></th>
                  <th scope="col"><div className="slds-truncate" title="EV/EBITDA">EV/EBITDA</div></th>
                  <th scope="col"><div className="slds-truncate" title="P/S">P/S</div></th>
                  <th scope="col"><div className="slds-truncate" title="Price">Price</div></th>
                </tr>
              </thead>
              <tbody>
                {peers.map((p) => (
                  <tr key={p.ticker}>
                    <td><div className="slds-truncate">{p.ticker}</div></td>
                    <td><div className="slds-truncate">{p.name}</div></td>
                    <td>{p.peRatio.toFixed(1)}</td>
                    <td>{p.evEbitda.toFixed(1)}</td>
                    <td>{p.psRatio.toFixed(1)}</td>
                    <td>${formatPrice(p.currentPrice)}</td>
                  </tr>
                ))}
                {peerAvg && (
                  <tr className="slds-text-title_bold">
                    <td colSpan={2}><div className="slds-truncate">Sector Avg</div></td>
                    <td>{peerAvg.peRatio.toFixed(1)}</td>
                    <td>{peerAvg.evEbitda.toFixed(1)}</td>
                    <td>{peerAvg.psRatio.toFixed(1)}</td>
                    <td>${formatPrice(peerAvg.currentPrice)}</td>
                  </tr>
                )}
              </tbody>
            </table>
            {valuationData?.compsRelativeValuation && (
              <div className="slds-p-around_small slds-text-body_small slds-text-color_weak">
                <p>{valuationData.compsRelativeValuation.peVsPeers}</p>
                <p>{valuationData.compsRelativeValuation.evEbitdaVsPeers}</p>
                <p>{valuationData.compsRelativeValuation.psVsPeers}</p>
              </div>
            )}
          </div>
        </article>
      )}
    </div>
  );
}
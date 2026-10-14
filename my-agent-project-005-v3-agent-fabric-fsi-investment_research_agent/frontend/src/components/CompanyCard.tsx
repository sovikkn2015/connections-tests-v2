/**
 * Enhanced Company Profile Dashboard — SLDS card with price header,
 * metrics grid, 52-week range bar, moving averages, and sentiment.
 */

import { useAgentStore } from '../store/agentStore';
import { formatPct, daysUntil } from '../services/responseParser';

export default function CompanyCard() {
  const { companyData, sentimentData, dataSource, researchLoading, researchError } = useAgentStore();

  /* ── Loading state ── */
  if (researchLoading) {
    return (
      <div
        className="slds-p-around_large slds-text-align_center"
        role="status"
        aria-label="Loading research data"
      >
        <div className="slds-spinner_container slds-is-relative slds-m-bottom_medium" style={{ height: '3rem' }}>
          <div role="status" className="slds-spinner slds-spinner_medium slds-spinner_brand">
            <span className="slds-assistive-text">Loading</span>
            <div className="slds-spinner__dot-a"></div>
            <div className="slds-spinner__dot-b"></div>
          </div>
        </div>
        <p className="slds-text-body_regular slds-text-color_weak">
          Loading research data...
        </p>
      </div>
    );
  }

  /* ── Error state ── */
  if (researchError) {
    return (
      <div
        className="slds-notify slds-notify_alert slds-alert_error slds-m-around_medium"
        role="alert"
        aria-label="Research data error"
      >
        <span className="slds-assistive-text">Error</span>
        <h2 className="slds-text-body_regular">
          {researchError}
        </h2>
      </div>
    );
  }


  if (!companyData) {
    return (
      <div
        className="slds-illustration slds-illustration_small slds-p-around_large slds-text-align_center"
        role="status"
        aria-label="No company data loaded"
      >
        <svg
          className="slds-illustration__svg slds-m-bottom_small"
          xmlns="http://www.w3.org/2000/svg"
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#b0adab"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <p className="slds-text-body_regular slds-text-color_weak">
          Ask the agent about a company to see details here.
        </p>
      </div>
    );
  }

  /* ── Derived values ── */
  const price = companyData.price ?? 0;
  const change = companyData.change ?? 0;
  const changePct = companyData.changePct ?? 0;
  const isPositive = change >= 0;
  const changeColor = isPositive ? '#04844b' : '#c23934';
  const changeSign = isPositive ? '+' : '';

  const low52 = parseFloat(companyData.weekLow52?.replace(/[$,]/g, '') || '0');
  const high52 = parseFloat(companyData.weekHigh52?.replace(/[$,]/g, '') || '0');
  const rangeSpan = high52 - low52;
  const rangePosition = rangeSpan > 0 ? ((price - low52) / rangeSpan) * 100 : 50;
  const clampedPosition = Math.max(0, Math.min(100, rangePosition));

  const earningsDays = companyData.earningsDate ? daysUntil(companyData.earningsDate) : null;

  /* ── Sentiment helpers ── */
  const sentimentEmoji =
    sentimentData?.overallSentiment === 'Bullish'
      ? '🟢'
      : sentimentData?.overallSentiment === 'Bearish'
        ? '🔴'
        : '🟡';
  const sentimentBg =
    sentimentData?.overallSentiment === 'Bullish'
      ? '#04844b'
      : sentimentData?.overallSentiment === 'Bearish'
        ? '#c23934'
        : '#ff9e2c';

  /* ── Metrics grid data ── */
  const metrics = [
    { label: 'Market Cap', value: companyData.marketCap },
    { label: 'P/E Ratio', value: companyData.peRatio },
    { label: 'Forward P/E', value: companyData.forwardPE },
    { label: 'EPS (TTM)', value: companyData.epsttm },
    { label: 'Beta', value: companyData.beta },
    { label: 'Dividend Yield', value: companyData.dividendYield },
    { label: 'Profit Margin', value: companyData.profitMargin },
    { label: 'Rev/Share', value: companyData.revenuePerShare },
  ];

  return (
    <article className="slds-card" aria-label={`Company profile for ${companyData.name}`}>
      <div className="slds-card__body slds-card__body_inner">
        {/* ── 1. Price Header Bar ── */}
        <div
          className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-around_small slds-m-bottom_small"
          style={{ background: '#f4f6f9', borderRadius: '6px' }}
          role="banner"
          aria-label="Price header"
        >
          <div className="slds-col">
            <span className="slds-text-heading_small">{companyData.name}</span>
            <span className="slds-badge slds-m-left_x-small" aria-label={`Ticker: ${companyData.ticker}`}>
              {companyData.ticker}
            </span>
            <span className="slds-badge slds-badge_inverse slds-m-left_xx-small" aria-label={`Exchange: ${companyData.exchange}`}>
              {companyData.exchange}
            </span>
            <span className="slds-badge slds-badge_inverse slds-m-left_xx-small" aria-label={`Sector: ${companyData.sector}`}>
              {companyData.sector}
            </span>
          </div>
          <div className="slds-col slds-text-align_right">
            <span style={{ fontSize: '1.5rem', fontWeight: 700 }} aria-label={`Current price ${price.toFixed(2)}`}>
              ${price.toFixed(2)}
            </span>
            {dataSource === 'live' && (
              <span
                className="slds-badge slds-m-left_xx-small"
                style={{ background: '#04844b', color: '#fff', fontSize: '0.65rem', verticalAlign: 'middle' }}
                aria-label="Live data"
              >
                LIVE
              </span>
            )}
            {dataSource === 'seed' && (
              <span
                className="slds-badge slds-m-left_xx-small"
                style={{ background: '#b0adab', color: '#fff', fontSize: '0.65rem', verticalAlign: 'middle' }}
                aria-label="Seed data"
              >
                SEED DATA
              </span>
            )}
            <span
              className="slds-m-left_x-small slds-text-body_regular"
              style={{ color: changeColor, fontWeight: 600 }}
              aria-label={`Change ${changeSign}${change.toFixed(2)} (${formatPct(changePct)})`}
            >
              {changeSign}${Math.abs(change).toFixed(2)} ({formatPct(changePct)})
            </span>
          </div>
        </div>

        {/* ── 2. Company Description ── */}
        {companyData.description && (
          <p className="slds-text-body_regular slds-m-bottom_small">
            {companyData.description}
          </p>
        )}

        {/* ── 3. Key Metrics Grid ── */}
        <div className="ir-metrics-grid slds-m-bottom_small" role="list" aria-label="Key financial metrics">
          {metrics.map(({ label, value }) => (
            <div
              key={label}
              className="slds-p-around_small"
              style={{ background: '#f4f6f9', borderRadius: '4px' }}
              role="listitem"
              aria-label={`${label}: ${value || '—'}`}
            >
              <p className="slds-text-body_small slds-text-color_weak">{label}</p>
              <p className="slds-text-body_regular" style={{ fontWeight: 600 }}>
                {value || '—'}
              </p>
            </div>
          ))}
        </div>

        {/* ── 4. 52-Week Range Bar ── */}
        <div className="slds-m-bottom_small" aria-label="52-week price range">
          <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_xx-small">
            52-Week Range
          </p>
          <div className="slds-grid slds-grid_vertical-align-center" style={{ gap: '0.5rem' }}>
            <span className="slds-text-body_small">{companyData.weekLow52}</span>
            <div
              className="ir-range-bar slds-col"
              role="img"
              aria-label={`Current price ${price.toFixed(2)} within 52-week range ${companyData.weekLow52} to ${companyData.weekHigh52}`}
            >
              <div
                className="ir-range-marker"
                style={{ left: `${clampedPosition}%` }}
                aria-hidden="true"
              />
            </div>
            <span className="slds-text-body_small">{companyData.weekHigh52}</span>
          </div>
        </div>

        {/* ── 5. Moving Averages ── */}
        {(companyData.movingAvg50 || companyData.movingAvg200) && (
          <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_small">
            50-day: {companyData.movingAvg50 || '—'} | 200-day: {companyData.movingAvg200 || '—'}
          </p>
        )}

        {/* ── 6. Bottom Info Bar ── */}
        <div
          className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-around_small"
          style={{ background: '#f4f6f9', borderRadius: '6px' }}
        >
          {/* Sentiment */}
          <div className="slds-col">
            {sentimentData ? (
              <span
                className="slds-badge"
                style={{ background: sentimentBg, color: '#fff' }}
                aria-label={`Sentiment: ${sentimentData.overallSentiment}, confidence ${sentimentData.confidence}`}
              >
                {sentimentEmoji} {sentimentData.overallSentiment} · {sentimentData.confidence} confidence
              </span>
            ) : (
              <span className="slds-text-body_small slds-text-color_weak">No sentiment data</span>
            )}
          </div>

          {/* Next Earnings */}
          <div className="slds-col slds-text-align_right">
            {companyData.earningsDate ? (
              <span className="slds-text-body_small" aria-label={`Next earnings on ${companyData.earningsDate}`}>
                📅 Earnings: {companyData.earningsDate}
                {earningsDays !== null && (
                  <span className="slds-text-color_weak"> ({earningsDays}d away)</span>
                )}
              </span>
            ) : (
              <span className="slds-text-body_small slds-text-color_weak">No earnings date</span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

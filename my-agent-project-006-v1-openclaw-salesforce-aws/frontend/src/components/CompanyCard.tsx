/**
 * Enhanced Company Profile Dashboard — backend-agnostic, renders from Zustand state.
 */

import { useAgentStore } from '../store/agentStore';
import { formatPct, daysUntil } from '../services/responseParser';

export default function CompanyCard() {
  const { companyData, sentimentData } = useAgentStore();

  if (!companyData) {
    return (
      <div className="slds-p-around_large slds-text-align_center">
        <p className="slds-text-body_regular slds-text-color_weak">
          Ask the agent about a company to see details here.
        </p>
      </div>
    );
  }

  const price = companyData.price ?? 0;
  const change = companyData.change ?? 0;
  const changePct = companyData.changePct ?? 0;
  const isPositive = change >= 0;
  const changeColor = isPositive ? '#04844b' : '#c23934';
  const changeSign = isPositive ? '+' : '';
  const low52 = parseFloat(companyData.weekLow52?.replace(/[$,]/g, '') || '0');
  const high52 = parseFloat(companyData.weekHigh52?.replace(/[$,]/g, '') || '0');
  const rangeSpan = high52 - low52;
  const clampedPosition = Math.max(0, Math.min(100, rangeSpan > 0 ? ((price - low52) / rangeSpan) * 100 : 50));
  const earningsDays = companyData.earningsDate ? daysUntil(companyData.earningsDate) : null;
  const sentimentBg = sentimentData?.overallSentiment === 'Bullish' ? '#04844b' : sentimentData?.overallSentiment === 'Bearish' ? '#c23934' : '#ff9e2c';

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
        <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-around_small slds-m-bottom_small" style={{ background: '#f4f6f9', borderRadius: '6px' }}>
          <div className="slds-col">
            <span className="slds-text-heading_small">{companyData.name}</span>
            <span className="slds-badge slds-m-left_x-small">{companyData.ticker}</span>
            <span className="slds-badge slds-badge_inverse slds-m-left_xx-small">{companyData.exchange}</span>
            <span className="slds-badge slds-badge_inverse slds-m-left_xx-small">{companyData.sector}</span>
          </div>
          <div className="slds-col slds-text-align_right">
            <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>${price.toFixed(2)}</span>
            <span className="slds-m-left_x-small" style={{ color: changeColor, fontWeight: 600 }}>
              {changeSign}${Math.abs(change).toFixed(2)} ({formatPct(changePct)})
            </span>
          </div>
        </div>
        {companyData.description && <p className="slds-text-body_regular slds-m-bottom_small">{companyData.description}</p>}
        <div className="ir-metrics-grid slds-m-bottom_small" role="list">
          {metrics.map(({ label, value }) => (
            <div key={label} className="slds-p-around_small" style={{ background: '#f4f6f9', borderRadius: '4px' }} role="listitem">
              <p className="slds-text-body_small slds-text-color_weak">{label}</p>
              <p className="slds-text-body_regular" style={{ fontWeight: 600 }}>{value || '\u2014'}</p>
            </div>
          ))}
        </div>
        <div className="slds-m-bottom_small">
          <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_xx-small">52-Week Range</p>
          <div className="slds-grid slds-grid_vertical-align-center" style={{ gap: '0.5rem' }}>
            <span className="slds-text-body_small">{companyData.weekLow52}</span>
            <div className="ir-range-bar slds-col"><div className="ir-range-marker" style={{ left: `${clampedPosition}%` }} /></div>
            <span className="slds-text-body_small">{companyData.weekHigh52}</span>
          </div>
        </div>
        {(companyData.movingAvg50 || companyData.movingAvg200) && (
          <p className="slds-text-body_small slds-text-color_weak slds-m-bottom_small">
            50-day: {companyData.movingAvg50 || '\u2014'} | 200-day: {companyData.movingAvg200 || '\u2014'}
          </p>
        )}
        <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-p-around_small" style={{ background: '#f4f6f9', borderRadius: '6px' }}>
          <div className="slds-col">
            {sentimentData ? (
              <span className="slds-badge" style={{ background: sentimentBg, color: '#fff' }}>
                {sentimentData.overallSentiment} &middot; {sentimentData.confidence} confidence
              </span>
            ) : <span className="slds-text-body_small slds-text-color_weak">No sentiment data</span>}
          </div>
          <div className="slds-col slds-text-align_right">
            {companyData.earningsDate ? (
              <span className="slds-text-body_small">
                Earnings: {companyData.earningsDate}
                {earningsDays !== null && <span className="slds-text-color_weak"> ({earningsDays}d away)</span>}
              </span>
            ) : <span className="slds-text-body_small slds-text-color_weak">No earnings date</span>}
          </div>
        </div>
      </div>
    </article>
  );
}

/**
 * Analyst Consensus Dashboard — backend-agnostic, renders from Zustand state.
 */

import { useAgentStore } from '../store/agentStore';
import { formatPrice } from '../services/responseParser';

function ratingBadgeClass(rating: string): string {
  const r = rating.toLowerCase();
  if (r === 'buy' || r === 'overweight') return 'slds-badge slds-theme_success';
  if (r === 'hold') return 'slds-badge slds-theme_warning';
  if (r === 'sell' || r === 'underweight') return 'slds-badge slds-theme_error';
  return 'slds-badge';
}

function actionBadgeClass(action: string | undefined): string {
  if (!action) return 'slds-badge';
  const a = action.toLowerCase();
  if (a === 'upgraded') return 'slds-badge slds-theme_success';
  if (a === 'downgraded') return 'slds-badge slds-theme_error';
  return 'slds-badge';
}

export default function CoverageTable() {
  const { coverageData, consensusSummary } = useAgentStore();

  if (!coverageData || coverageData.length === 0) {
    return (
      <div className="slds-p-around_large slds-text-align_center">
        <p className="slds-text-body_regular slds-text-color_weak">
          Ask &quot;Who covers NVDA?&quot; to see analyst coverage.
        </p>
      </div>
    );
  }

  const buyCount = consensusSummary?.buyCount ?? 0;
  const holdCount = consensusSummary?.holdCount ?? 0;
  const sellCount = consensusSummary?.sellCount ?? 0;
  const total = buyCount + holdCount + sellCount;
  const lowTarget = consensusSummary?.lowTargetPrice ?? 0;
  const highTarget = consensusSummary?.highTargetPrice ?? 0;
  const avgTarget = consensusSummary?.avgTargetPrice ?? 0;
  const currentPrice = consensusSummary?.currentPrice ?? 0;
  const range = highTarget - lowTarget || 1;
  const currentPricePos = ((currentPrice - lowTarget) / range) * 100;
  const avgTargetPos = ((avgTarget - lowTarget) / range) * 100;

  return (
    <div className="slds-p-around_medium">
      {total > 0 && (
        <div className="slds-m-bottom_medium">
          <h3 className="slds-text-heading_small slds-m-bottom_x-small">Consensus Distribution</h3>
          <div style={{ display: 'flex', height: '28px', borderRadius: '4px', overflow: 'hidden' }}>
            {buyCount > 0 && <div style={{ width: `${(buyCount / total) * 100}%`, backgroundColor: '#04844b', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 600 }}>{buyCount}</div>}
            {holdCount > 0 && <div style={{ width: `${(holdCount / total) * 100}%`, backgroundColor: '#ffb75d', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3e3e3c', fontSize: '0.75rem', fontWeight: 600 }}>{holdCount}</div>}
            {sellCount > 0 && <div style={{ width: `${(sellCount / total) * 100}%`, backgroundColor: '#c23934', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 600 }}>{sellCount}</div>}
          </div>
          <p className="slds-text-body_small slds-text-color_weak slds-m-top_xx-small">{buyCount} Buy | {holdCount} Hold | {sellCount} Sell</p>
        </div>
      )}
      {consensusSummary && (
        <div className="slds-m-bottom_medium">
          <h3 className="slds-text-heading_small slds-m-bottom_x-small">Target Price Range</h3>
          <div style={{ position: 'relative', height: '32px', backgroundColor: '#e5e5e5', borderRadius: '4px', margin: '8px 0' }}>
            <div style={{ position: 'absolute', left: `${Math.min(Math.max(currentPricePos, 0), 100)}%`, top: '50%', transform: 'translate(-50%, -50%)', width: '14px', height: '14px', borderRadius: '50%', backgroundColor: '#1589ee', border: '2px solid #fff', zIndex: 2 }} />
            <div style={{ position: 'absolute', left: `${Math.min(Math.max(avgTargetPos, 0), 100)}%`, top: '50%', transform: 'translate(-50%, -50%) rotate(45deg)', width: '12px', height: '12px', backgroundColor: '#ff9a3c', border: '2px solid #fff', zIndex: 2 }} />
          </div>
          <div className="slds-grid slds-grid_spread slds-text-body_small slds-text-color_weak">
            <span>Low {formatPrice(lowTarget)}</span>
            <span style={{ color: '#1589ee', fontWeight: 600 }}>Current {formatPrice(currentPrice)}</span>
            <span style={{ color: '#ff9a3c', fontWeight: 600 }}>Avg {formatPrice(avgTarget)}</span>
            <span>High {formatPrice(highTarget)}</span>
          </div>
        </div>
      )}
      <table className="slds-table slds-table_cell-buffer slds-table_bordered slds-table_striped" aria-label="Analyst Coverage">
        <thead>
          <tr className="slds-line-height_reset">
            <th className="slds-text-title_caps" scope="col">Analyst</th>
            <th className="slds-text-title_caps" scope="col">Firm</th>
            <th className="slds-text-title_caps" scope="col">Rating</th>
            <th className="slds-text-title_caps" scope="col">Target</th>
            <th className="slds-text-title_caps" scope="col">Action</th>
            <th className="slds-text-title_caps" scope="col">Updated</th>
          </tr>
        </thead>
        <tbody>
          {coverageData.map((row, i) => (
            <tr key={i}>
              <td>{row.analyst}</td>
              <td>{row.firm}</td>
              <td><span className={ratingBadgeClass(row.rating)}>{row.rating}</span></td>
              <td>{row.targetPrice}</td>
              <td>{row.lastAction ? <span className={actionBadgeClass(row.lastAction)}>{row.lastAction}</span> : '\u2014'}</td>
              <td>{row.lastUpdated}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

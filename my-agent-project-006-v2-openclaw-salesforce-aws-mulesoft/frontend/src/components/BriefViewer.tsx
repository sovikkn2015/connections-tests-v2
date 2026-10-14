/**
 * Brief Viewer — structured display of completed research brief.
 * Sections: Executive Summary, Thesis, Catalysts, Risks, Valuation, Recommendation.
 */

import { useState } from 'react';
import { useAgentStore } from '../store/agentStore';
import * as openclawApi from '../services/openclawApi';

export default function BriefViewer() {
  const { briefData, sessionKey } = useAgentStore();
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<{ ok: boolean; message: string } | null>(null);

  if (!briefData) {
    return (
      <div className="slds-p-around_large slds-text-align_center">
        <p className="slds-text-body_regular slds-text-color_weak">
          Run a deep dive pipeline to generate a research brief.
        </p>
        <p className="slds-text-body_small slds-text-color_weak slds-m-top_x-small">
          Try: &quot;Deep dive on NVIDIA&quot;
        </p>
      </div>
    );
  }

  const handlePublish = async () => {
    setPublishing(true);
    setPublishResult(null);
    try {
      await openclawApi.sendMessage(
        `Publish research brief for ${briefData.ticker} to Salesforce CRM. Pipeline run: ${briefData.pipelineRunId}`,
        sessionKey,
        'fsi-research',
        {
          onText: () => {},
          onToolStart: () => {},
          onToolResult: () => {},
          onToolError: () => {},
          onLifecycle: () => {},
          onComplete: () => {
            setPublishResult({ ok: true, message: 'Brief published to Salesforce successfully.' });
            setPublishing(false);
          },
        },
      );
    } catch (err) {
      setPublishResult({ ok: false, message: (err as Error).message });
      setPublishing(false);
    }
  };

  const sections = [
    { title: 'Executive Summary', content: briefData.executiveSummary },
    { title: 'Investment Thesis', content: briefData.thesis },
    { title: 'Catalysts', content: briefData.catalysts },
    { title: 'Key Risks', content: briefData.risks },
    { title: 'Valuation', content: briefData.valuation },
  ];

  return (
    <div className="slds-p-around_medium" aria-label={`Research brief for ${briefData.company}`}>
      <div className="slds-grid slds-grid_align-spread slds-grid_vertical-align-center slds-m-bottom_medium slds-p-around_small" style={{ background: '#f4f6f9', borderRadius: 6 }}>
        <div>
          <p className="slds-text-heading_small">{briefData.company} ({briefData.ticker})</p>
          <p className="slds-text-body_small slds-text-color_weak">
            Analyst: {briefData.analyst} | Generated: {briefData.generatedDate}
          </p>
        </div>
        <div className="slds-text-align_right">
          <span className="slds-badge slds-theme_success" style={{ fontSize: '0.875rem' }}>
            {briefData.rating}
          </span>
          <p className="slds-text-body_small slds-m-top_xx-small">
            Target: ${briefData.targetPrice.toFixed(2)}
          </p>
        </div>
      </div>

      {sections.map((section) => (
        <div key={section.title} className="ir-brief-section">
          <h3 className="slds-text-heading_small slds-m-bottom_xx-small">{section.title}</h3>
          <p className="slds-text-body_regular" style={{ whiteSpace: 'pre-wrap' }}>{section.content}</p>
        </div>
      ))}

      <p className="slds-text-body_small slds-text-color_weak slds-m-top_small">
        Pipeline Run: {briefData.pipelineRunId}
      </p>

      {publishResult && (
        <div
          className={`slds-notify slds-notify_toast slds-m-top_small ${publishResult.ok ? 'slds-theme_success' : 'slds-theme_error'}`}
          role="status"
          style={{ padding: '0.5rem 1rem', borderRadius: 4 }}
        >
          <p className="slds-text-body_small">{publishResult.message}</p>
        </div>
      )}

      <div className="slds-m-top_medium">
        <button
          className="slds-button slds-button_brand"
          aria-label="Publish brief to Salesforce"
          onClick={handlePublish}
          disabled={publishing}
        >
          {publishing ? 'Publishing\u2026' : 'Publish to Salesforce'}
        </button>
        <button className="slds-button slds-button_neutral slds-m-left_small" aria-label="Export brief as PDF">
          Export PDF
        </button>
      </div>
    </div>
  );
}

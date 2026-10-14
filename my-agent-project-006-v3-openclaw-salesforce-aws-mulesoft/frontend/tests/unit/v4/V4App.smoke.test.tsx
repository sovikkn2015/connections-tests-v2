/**
 * V4 smoke tests — verify each persona renders its key scaffolding
 * without throwing. We don't assert pixel layout; vitest can't paint.
 * We do assert the defining structural elements:
 *   - persona header with correct brand + nav
 *   - research: brief pane + market pane + demand pane
 *   - advisor: queue tabs + conversation pane
 *   - client: phone bezel + WhatsApp header + disclaimer
 */

import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { V4App } from '../../../src/v4/V4App';
import { useSessionStore } from '../../../src/shared/store/session';
import { useBriefStore } from '../../../src/shared/store/brief';
import { useTraversalStore } from '../../../src/shared/store/traversal';
import { useQueuesStore } from '../../../src/shared/store/queues';

function renderV4(persona: 'research' | 'advisor' | 'client') {
  // Set URL so V4App picks the right persona
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      search: `?v4=1&persona=${persona}`,
      pathname: '/',
    },
    writable: true,
  });
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <V4App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useBriefStore.getState().reset();
  useTraversalStore.getState().reset();
  useQueuesStore.setState({
    itemsByQueue: { inbox: [], briefs: [], alerts: [], pending: [] },
    selectedItemId: null,
  });
  useSessionStore.setState({
    sessionToken: 'tok',
    principalId: 'dev',
    principalName: 'Dev User',
    persona: 'fsi_research',
    sessionId: 'sid',
    correlationId: 'cid',
    connectionStatus: 'open',
  });
});

describe('V4 research terminal', () => {
  it('renders the research persona header + brief pane + market pane + demand pane', () => {
    renderV4('research');
    expect(screen.getByTestId('v4-research')).toBeInTheDocument();
    expect(screen.getByRole('banner')).toBeInTheDocument();
    // "FSI Workforce 360" appears as the header brand AND (at simple map
    // level) as the coordinator node label — both are correct.
    expect(screen.getAllByText(/FSI Workforce 360/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Brief — citation-enforced/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Market · live/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Demand Signals/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders the trust spine strip with map + timeline', () => {
    renderV4('research');
    expect(screen.getByTestId('trust-spine-v4')).toBeInTheDocument();
    expect(screen.getByTestId('traversal-map-v4')).toBeInTheDocument();
    expect(screen.getByTestId('timeline-v4')).toBeInTheDocument();
  });

  it('renders the audit strip at the bottom', () => {
    renderV4('research');
    expect(screen.getByTestId('audit-strip-v4')).toBeInTheDocument();
  });

  it('renders a theme toggle button that toggles data-theme', () => {
    // Clear any persisted theme so we start with a known system default.
    try {
      window.localStorage.removeItem('v4.theme');
    } catch {
      /* ignore */
    }
    renderV4('research');
    const toggle = screen.getByTestId('v4-theme-toggle');
    expect(toggle).toBeInTheDocument();
    const root = document.querySelector('.v4-root') as HTMLElement;
    const initial = root.dataset.theme;
    act(() => {
      toggle.click();
    });
    // After click, the data-theme attribute must have flipped.
    expect(root.dataset.theme).not.toBe(initial);
    expect(['dark', 'light']).toContain(root.dataset.theme);
  });

  it('traversal map: simple level (default) shows only the named specialists for the active persona', () => {
    renderV4('research');
    // Simple view shows the analyst-friendly set
    expect(screen.getByTestId('v4-map-node-research_orchestrator')).toBeInTheDocument();
    expect(screen.getByTestId('v4-map-node-market_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v4-map-node-filings_specialist')).toBeInTheDocument();
    expect(screen.getByTestId('v4-map-node-sentiment_specialist')).toBeInTheDocument();
    // Developer-only ids should NOT be visible at simple level
    expect(screen.queryByTestId('v4-map-node-skill:rag_retrieve')).toBeNull();
    expect(screen.queryByTestId('v4-map-node-skill:financial_statement_analysis')).toBeNull();
  });

  it('traversal map: switching to Developer level renders the full topology', () => {
    renderV4('research');
    const developerTab = screen.getByTestId('v4-map-level-developer');
    act(() => {
      developerTab.click();
    });
    // Every specialist in topology is now visible
    for (const spec of [
      'action_specialist',
      'suitability_specialist',
      'portfolio_specialist',
      'faq_specialist',
    ]) {
      expect(screen.getByTestId(`v4-map-node-${spec}`)).toBeInTheDocument();
    }
    // MCPs visible
    for (const mcp of ['market-data', 'sec-edgar', 'news-search', 'salesforce-crm', 'mulesoft-actions']) {
      expect(screen.getByTestId(`v4-map-node-${mcp}`)).toBeInTheDocument();
    }
  });

  it('traversal map renders a plain-English caption under the map', () => {
    renderV4('research');
    const caption = screen.getByTestId('v4-map-caption');
    expect(caption.textContent).toMatch(/Research Analyst/i);
    expect(caption.textContent).toMatch(/material non-public information/i);
  });
});

describe('V4 advisor workbench', () => {
  it('renders the three-column body with queue tabs + conversation + client 360', () => {
    renderV4('advisor');
    expect(screen.getByTestId('v4-advisor')).toBeInTheDocument();
    // Queue tabs: Actions / Insights / Tasks
    expect(screen.getByRole('tab', { name: /Actions/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Insights/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Tasks/i })).toBeInTheDocument();
    // Conversation composer
    expect(screen.getByLabelText(/Advisor composer/i)).toBeInTheDocument();
    // Client 360 column
    expect(screen.getByLabelText(/Client 360/i)).toBeInTheDocument();
  });
});

describe('V4 client channel', () => {
  it('renders the phone bezel with channel header and WhatsApp disclaimer', () => {
    renderV4('client');
    expect(screen.getByTestId('v4-client')).toBeInTheDocument();
    // Channel header brand
    expect(screen.getByText(/Your Wealth Team/i)).toBeInTheDocument();
    // Disclaimer text is persistent on the WhatsApp surface
    expect(screen.getByText(/For informational purposes/i)).toBeInTheDocument();
    // Two caption columns
    expect(screen.getByText(/Channel-native, not a portal\./i)).toBeInTheDocument();
    expect(screen.getByText(/One trust spine\./i)).toBeInTheDocument();
  });
});

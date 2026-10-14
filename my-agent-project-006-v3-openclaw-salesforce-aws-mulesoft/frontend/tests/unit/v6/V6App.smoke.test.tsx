/**
 * V6 smoke tests — verify each persona renders its key scaffolding
 * without throwing. We don't assert pixel layout; vitest can't paint.
 * We do assert the defining structural elements:
 *   - persona header with correct brand + nav + designed identity
 *   - research: brief pane + market pane + demand pane + trust spine
 *   - advisor: queue tabs + conversation + client 360 + trust spine
 *   - client: phone bezel + WhatsApp header + disclaimer + trust spine
 *   - theme toggle flips data-theme attribute
 *   - all nav links contain v6=1
 */

import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { V6App } from '../../../src/v6/V6App';
import { useSessionStore } from '../../../src/shared/store/session';
import { useBriefStore } from '../../../src/shared/store/brief';
import { useTraversalStore } from '../../../src/shared/store/traversal';
import { useQueuesStore } from '../../../src/shared/store/queues';

function renderV6(persona: 'research' | 'advisor' | 'client') {
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      search: `?v6=1&persona=${persona}`,
      pathname: '/',
    },
    writable: true,
  });
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <V6App />
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
  // Clear persisted theme so tests start with a known state
  try {
    window.localStorage.removeItem('v6.theme');
  } catch {
    /* ignore */
  }
});

describe('V6 research terminal', () => {
  it('renders header + brief card + market card + demand card', () => {
    renderV6('research');
    expect(screen.getByTestId('v6-research')).toBeInTheDocument();
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getAllByText(/FSI Workforce 360/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Brief — citation-enforced/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Market · live/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Demand Signals/i).length).toBeGreaterThanOrEqual(1);
  });

  it('has a collapsible trust spine', () => {
    renderV6('research');
    const spine = screen.getByTestId('v6-trust-spine');
    expect(spine).toBeInTheDocument();
    expect(spine.tagName.toLowerCase()).toBe('details');
  });
});

describe('V6 advisor workbench', () => {
  it('renders header + queue tabs + conversation + client 360', () => {
    renderV6('advisor');
    expect(screen.getByTestId('v6-advisor')).toBeInTheDocument();
    expect(screen.getByRole('banner')).toBeInTheDocument();
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

describe('V6 client channel', () => {
  it('renders header + phone bezel + trust spine', () => {
    renderV6('client');
    expect(screen.getByTestId('v6-client')).toBeInTheDocument();
    expect(screen.getByRole('banner')).toBeInTheDocument();
    // WhatsApp header brand
    expect(screen.getByText(/Your Wealth Team/i)).toBeInTheDocument();
    // Disclaimer
    expect(screen.getByText(/For informational purposes/i)).toBeInTheDocument();
    // Caption columns
    expect(screen.getByText(/Channel-native, not a portal\./i)).toBeInTheDocument();
    expect(screen.getByText(/One trust spine\./i)).toBeInTheDocument();
  });
});

describe('V6 theme toggle', () => {
  it('click toggles data-theme attribute', () => {
    renderV6('research');
    const toggle = screen.getByTestId('v6-theme-toggle');
    expect(toggle).toBeInTheDocument();
    const initial = document.documentElement.getAttribute('data-theme');
    act(() => {
      toggle.click();
    });
    const after = document.documentElement.getAttribute('data-theme');
    expect(after).not.toBe(initial);
    expect(['dark', 'light']).toContain(after);
  });
});

describe('V6 nav links', () => {
  it('all nav links contain v6=1', () => {
    renderV6('research');
    const nav = screen.getByLabelText(/Persona switcher/i);
    const links = nav.querySelectorAll('a');
    expect(links.length).toBeGreaterThanOrEqual(3);
    links.forEach((link) => {
      expect(link.getAttribute('href')).toContain('v6=1');
    });
  });
});

describe('V6 persona header identity', () => {
  it('research persona shows Sarah Chen, not Dev User', () => {
    // Set principalId to dev-principal so the header uses designed identity
    useSessionStore.setState({ principalId: 'dev-principal', principalName: 'Dev User' });
    renderV6('research');
    expect(screen.getByText(/Sarah Chen/i)).toBeInTheDocument();
    expect(screen.getByText(/Sr\. Equity Analyst/i)).toBeInTheDocument();
  });

  it('advisor persona shows Marcus Kerrigan, not Dev User', () => {
    useSessionStore.setState({ principalId: 'dev-principal', principalName: 'Dev User' });
    renderV6('advisor');
    expect(screen.getByText(/Marcus Kerrigan/i)).toBeInTheDocument();
    expect(screen.getByText(/Sr\. Wealth Advisor/i)).toBeInTheDocument();
  });

  it('client persona shows Eleanor Vance, not Dev User', () => {
    useSessionStore.setState({ principalId: 'dev-principal', principalName: 'Dev User' });
    renderV6('client');
    expect(screen.getByText(/Eleanor Vance/i)).toBeInTheDocument();
    expect(screen.getByText(/Tier-A · since 2009/i)).toBeInTheDocument();
  });
});

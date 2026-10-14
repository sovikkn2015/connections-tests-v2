/**
 * V6App — SLDS-inspired light theme (default) with dark toggle.
 *
 * Activation: `?v6=1` or `?ui=v6` on the URL.
 *
 * Theme management:
 *  - Persists to localStorage key `v6.theme`
 *  - Defaults to system preference (prefers-color-scheme)
 *  - Applies `data-theme` attribute on the document root element
 *
 * All three personas route through V6-specific components that import
 * V4 atoms (TraversalMapV4, TimelineV4, AuditStripV4, etc.) for the
 * trust spine and audit strip.
 */

import { useCallback, useEffect, useState } from 'react';
import { ResearchTerminalV6 } from './personas/ResearchTerminalV6';
import { AdvisorWorkbenchV6 } from './personas/AdvisorWorkbenchV6';
import { ClientChannelV6 } from './personas/ClientChannelV6';
import { personaFromRoute } from '../shared/types/persona';

import '../v4/styles/fonts.css';
import '../v4/styles/fsi-design-system.css';
import './styles/v6.css';

const THEME_KEY = 'v6.theme';

function getInitialTheme(): 'light' | 'dark' {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    /* localStorage unavailable */
  }
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

export interface V6AppProps {
  onAuthExpired?: () => void;
}

export function V6App({ onAuthExpired }: V6AppProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme);

  // Apply data-theme on root element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* localStorage unavailable */
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  const persona =
    typeof window !== 'undefined'
      ? personaFromRoute(new URLSearchParams(window.location.search).get('persona'))
      : 'fsi_research';

  return (
    <div className="v6-root" data-testid="v6-root" data-persona={persona}>
      {persona === 'fsi_research' && (
        <ResearchTerminalV6 onAuthExpired={onAuthExpired} theme={theme} onToggleTheme={toggleTheme} />
      )}
      {persona === 'fsi_advisor' && (
        <AdvisorWorkbenchV6 onAuthExpired={onAuthExpired} theme={theme} onToggleTheme={toggleTheme} />
      )}
      {persona === 'fsi_client_liaison' && (
        <ClientChannelV6 onAuthExpired={onAuthExpired} theme={theme} onToggleTheme={toggleTheme} />
      )}
    </div>
  );
}

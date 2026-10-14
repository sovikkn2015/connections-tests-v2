/**
 * V4App — FSI Workforce 360 disciplined rebuild.
 *
 * Activation: `?v4=1` on the URL. Routes by `?persona=` exactly like
 * v3 / v2 / v1. Independent subtree — nothing v1/v2/v3 changes.
 *
 * Design system: ported verbatim from the uploaded UIUX Design zip
 * (`docs/UIUX Design.zip`). No ad-hoc CSS; every measurement comes from
 * the designer's original file. That's why V4 reads sharper than V3.
 *
 * No light/dark toggle — industry platforms (Bloomberg, FactSet)
 * don't ship one on analyst surfaces and the v3 toggle diluted the
 * aesthetic.
 */

import { ResearchTerminalV4 } from './personas/ResearchTerminalV4';
import { AdvisorWorkbenchV4 } from './personas/AdvisorWorkbenchV4';
import { ClientChannelV4 } from './personas/ClientChannelV4';
import { useTheme } from './theme/useTheme';
import { personaFromRoute } from '../shared/types/persona';

import './styles/fonts.css';
import './styles/fsi-design-system.css';

export interface V4AppProps {
  onAuthExpired?: () => void;
}

export function V4App({ onAuthExpired }: V4AppProps) {
  // Initialize the theme before persona mounts so data-theme is applied on
  // the first paint (no dark→light flicker in light-mode sessions).
  useTheme();

  const persona =
    typeof window !== 'undefined'
      ? personaFromRoute(new URLSearchParams(window.location.search).get('persona'))
      : 'fsi_research';

  return (
    <div className="v4-root" data-testid="v4-root" data-persona={persona}>
      {persona === 'fsi_research' && <ResearchTerminalV4 onAuthExpired={onAuthExpired} />}
      {persona === 'fsi_advisor' && <AdvisorWorkbenchV4 onAuthExpired={onAuthExpired} />}
      {persona === 'fsi_client_liaison' && <ClientChannelV4 onAuthExpired={onAuthExpired} />}
    </div>
  );
}

/**
 * V5App — V4 components + V5 surface-hierarchy CSS overrides.
 *
 * This is the version that works: V4's layout (3-column body, collapsible
 * trust spine, plain-English map) with V5's visual refinement (surface
 * hierarchy, spacing rhythm, border removal, visual anchor, typography).
 *
 * All three personas render through V4's components. The v5-overrides.css
 * layers on top via the `.v5-root` class.
 *
 * Activation: `?v5=1` on the URL.
 */

import { ResearchTerminalV4 } from '../v4/personas/ResearchTerminalV4';
import { AdvisorWorkbenchV4 } from '../v4/personas/AdvisorWorkbenchV4';
import { ClientChannelV4 } from '../v4/personas/ClientChannelV4';
import { useTheme } from '../v4/theme/useTheme';
import { personaFromRoute } from '../shared/types/persona';

import '../v4/styles/fonts.css';
import '../v4/styles/fsi-design-system.css';
import './styles/v5-overrides.css';

export interface V5AppProps {
  onAuthExpired?: () => void;
}

export function V5App({ onAuthExpired }: V5AppProps) {
  useTheme();

  const persona =
    typeof window !== 'undefined'
      ? personaFromRoute(new URLSearchParams(window.location.search).get('persona'))
      : 'fsi_research';

  return (
    <div className="v4-root v5-root" data-testid="v5-root" data-persona={persona}>
      {persona === 'fsi_research' && <ResearchTerminalV4 onAuthExpired={onAuthExpired} />}
      {persona === 'fsi_advisor' && <AdvisorWorkbenchV4 onAuthExpired={onAuthExpired} />}
      {persona === 'fsi_client_liaison' && <ClientChannelV4 onAuthExpired={onAuthExpired} />}
    </div>
  );
}

/**
 * V2App — v2 persona router. Rendered inside a `.v2-root` wrapper so the v2
 * design tokens and component styles scope correctly without bleeding into
 * the existing v1 UI.
 *
 * Activation: `?persona=<key>&v2=1` (or `?ui=v2`). The v1 UI remains the
 * default so existing demo links and tests keep working untouched.
 */

import { useMemo } from 'react';
import { ResearchTerminalV2 } from './personas/ResearchTerminalV2';
import { AdvisorWorkbenchV2 } from './personas/AdvisorWorkbenchV2';
import { ClientChannelV2 } from './personas/ClientChannelV2';
import { RestClient } from '../shared/lib/restClient';
import { useSessionStore } from '../shared/store/session';
import { personaFromRoute } from '../shared/types/persona';
import './styles/tokens.css';
import './styles/header.css';
import './styles/map.css';
import './styles/timeline.css';
import './styles/gates.css';
import './styles/personas.css';

export interface V2AppProps {
  onAuthExpired?: () => void;
}

export function V2App({ onAuthExpired }: V2AppProps) {
  const personaParam =
    typeof window !== 'undefined'
      ? new URLSearchParams(window.location.search).get('persona')
      : null;
  const persona = personaFromRoute(personaParam);
  const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
  const rest = useMemo(
    () => new RestClient(apiUrl, () => useSessionStore.getState().sessionToken ?? ''),
    [apiUrl],
  );

  return (
    <div className="v2-root" data-testid="v2-root">
      {persona === 'fsi_research' && (
        <ResearchTerminalV2 rest={rest} onAuthExpired={onAuthExpired} />
      )}
      {persona === 'fsi_advisor' && <AdvisorWorkbenchV2 onAuthExpired={onAuthExpired} />}
      {persona === 'fsi_client_liaison' && <ClientChannelV2 onAuthExpired={onAuthExpired} />}
    </div>
  );
}

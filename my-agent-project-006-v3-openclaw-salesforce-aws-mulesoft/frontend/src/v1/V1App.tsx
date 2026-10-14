/**
 * V1App — v1 persona router. Renders the original three persona surfaces:
 *   - ResearchTerminal (Sarah)
 *   - AdvisorScreen (Marcus) — also hosts AlertQueue when ?view=alerts
 *   - ClientChannel (Eleanor)
 *
 * Kept symmetrical to V2App so App.tsx can cleanly switch between them.
 */

import { useMemo } from 'react';
import { ResearchTerminal } from './personas/research/ResearchTerminal';
import { AdvisorScreen } from './personas/advisor/AdvisorScreen';
import { AlertQueue } from './personas/advisor/AlertQueue';
import { ClientChannel } from './personas/client/ClientChannel';
import { RestClient } from '../shared/lib/restClient';
import { useSessionStore } from '../shared/store/session';
import { personaFromRoute } from '../shared/types/persona';

export interface V1AppProps {
  onAuthExpired?: () => void;
}

export function V1App({ onAuthExpired }: V1AppProps) {
  const persona =
    typeof window !== 'undefined'
      ? personaFromRoute(new URLSearchParams(window.location.search).get('persona'))
      : 'fsi_research';
  const view =
    typeof window !== 'undefined'
      ? new URLSearchParams(window.location.search).get('view')
      : null;

  const apiUrl = (import.meta.env.VITE_API_URL ?? '') as string;
  const rest = useMemo(
    () => new RestClient(apiUrl, () => useSessionStore.getState().sessionToken ?? ''),
    [apiUrl],
  );

  return (
    <>
      {persona === 'fsi_research' && (
        <ResearchTerminal rest={rest} onAuthExpired={onAuthExpired} />
      )}
      {persona === 'fsi_advisor' && view === 'alerts' && <AlertQueue />}
      {persona === 'fsi_advisor' && view !== 'alerts' && (
        <AdvisorScreen onAuthExpired={onAuthExpired} />
      )}
      {persona === 'fsi_client_liaison' && (
        <ClientChannel onAuthExpired={onAuthExpired} />
      )}
    </>
  );
}

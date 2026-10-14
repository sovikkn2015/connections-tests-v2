/**
 * Three personas — one runtime, three entry configs.
 * Must match openclaw.json persona keys and the Pydantic SessionContext validator
 * in openclaw/orchestration/messages.py.
 */

export type Persona = 'fsi_research' | 'fsi_advisor' | 'fsi_client_liaison';

export const PERSONAS: readonly Persona[] = [
  'fsi_research',
  'fsi_advisor',
  'fsi_client_liaison',
] as const;

export const PERSONA_LABEL: Record<Persona, string> = {
  fsi_research: 'Research Terminal',
  fsi_advisor: 'Advisor Workbench',
  fsi_client_liaison: 'Client Channel',
};

export type PersonaRouteKey = 'research' | 'advisor' | 'client';

export const PERSONA_FROM_ROUTE: Record<PersonaRouteKey, Persona> = {
  research: 'fsi_research',
  advisor: 'fsi_advisor',
  client: 'fsi_client_liaison',
};

export const PERSONA_TO_ROUTE: Record<Persona, PersonaRouteKey> = {
  fsi_research: 'research',
  fsi_advisor: 'advisor',
  fsi_client_liaison: 'client',
};

export function personaFromRoute(value: string | null): Persona {
  if (!value) return 'fsi_research';
  const key = value.toLowerCase() as PersonaRouteKey;
  return PERSONA_FROM_ROUTE[key] ?? 'fsi_research';
}

"""
M1 Agent Identity Service — Project 007 FSI Interoperability Platform.

Issues, verifies, and revokes Agent Identity Documents (AIDs).
JWT RS256 tokens with FSI-specific claims: LEI, CRD, archetype, role,
authority_scope, authority_excludes, jurisdiction, pod_id, client_scope.

Keycloak handles user authentication (OAuth 2.0/OIDC/SAML).
M1 builds the AID schema on top — the FSI identity layer.

Called by: M2, M4, M6, M8, M9, M10 (foundational module).
No cross-module imports. All callers use REST endpoints.
"""

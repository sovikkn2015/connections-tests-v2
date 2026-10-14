---
inclusion: fileMatch
fileMatchPattern: "my-agent-project-007-fsi-interoperability/**"
---

# Project 007: FSI Interoperability Platform — Steering

## Design Documents (Source of Truth)
- #[[file:my-agent-project-007-fsi-interoperability/docs/007-consolidated-design-and-plan.md]]
- #[[file:my-agent-project-007-fsi-interoperability/docs/architecture/ARCH-07-definitive-tech-stack.md]]
- #[[file:my-agent-project-007-fsi-interoperability/docs/architecture/ARCH-09-complete-module-map.md]]
- #[[file:my-agent-project-007-fsi-interoperability/docs/implementation/IMPL-06-blocker-resolution-plan.md]]

## Build Process (Non-Negotiable)
- #[[file:my-agent-project-007-fsi-interoperability/docs/007-module-build-playbook.md]]
- Every module follows the 7-step playbook: Spec → LLMJ Review → Fix → Re-Review (7.5+) → Build → Verify Tests → Complete
- DO NOT skip steps. DO NOT build without a GO-reviewed spec.

## Architecture Rules (Non-Negotiable)

### Agent Runtime
1. Cloud (Tier 3/4): Claude Managed Agents is the default runtime. Strands SDK for hybrid/on-prem only.
2. OpenClaw is the channel gateway only (12+ channels). It does NOT orchestrate agents.
3. Runtime is a Helm values toggle, not a code change. Application code is identical across topologies.

### Trust Layer (THE MOAT — M1+M2+M4+M6+M10)
4. Every MCP call MUST pass through M6 Trust-Aware Gateway. No direct vendor API calls.
5. M2/M4 policy evaluation is OPA/Rego ONLY. Compliance checks are NEVER done by LLM.
6. M10 audit writes to THREE tiers: Langfuse + S3 Object Lock WORM + CRM. All three required.
7. MNPI fields NEVER sent to LLM prompts or agent memory unfiltered. M4 filters BEFORE LLM.
8. Fail-closed on ANY compliance check failure. No degraded mode that bypasses trust.

### Modules
9. 13 modules (M1-M13). Module boundaries are strict. No cross-module imports.
10. M11 is POLYGLOT: TypeScript for REST, Python for BLPAPI/gRPC/SFTP. Each adapter is its own container.
11. M13 FIX Bridge is a SEPARATE module from M11. Stateful. Uses StatefulSet + PersistentVolume.
12. M3 canonical schema has 18 types. Household is a CONTAINER model (vendor mappings, not unified).

### LLM
13. Bedrock Claude Sonnet for research. Bedrock Claude Haiku for routing/conversation/execution.
14. NO LLM for compliance (M2/M4 is deterministic OPA).
15. LLM provider is abstracted. Swappable via config (Bedrock/Azure/GCP/self-hosted).

### Compliance
16. Cost basis normalization is REQUIRED in M7 translators. cost_basis_method field is never null.
17. Principal review queue (FINRA 2210) required for BD communications. OPA classifies retail vs institutional.
18. Smarsh archiving required before any BD deployment. Phase 2 lighthouse is RIA-only.
19. Every OPA rule must include wsp_section annotation for WSP-to-YAML mapping.

### Security
20. Zero credentials in git. All secrets via HashiCorp Vault or AWS Secrets Manager.
21. mTLS between ALL modules (cert-manager, 24hr rotation).
22. Private subnets only for data plane. PrivateLink for Bedrock. No public internet for MNPI.
23. Per-tenant KMS key. Namespace isolation. NetworkPolicy per module.

### Deployment
24. docker-compose.yml for local dev. Helm umbrella chart for production.
25. 3 topologies: cloud (values-cloud.yaml), hybrid (values-hybrid.yaml), on-prem (values-onprem.yaml).
26. GitOps via ArgoCD. CI/CD via GitHub Actions.
27. Phase 5 (Tier 1) is DEFERRED. Do not build on-prem topology until funded.

### Build Strategy (Non-Negotiable)
- #[[file:my-agent-project-007-fsi-interoperability/docs/007-build-strategy.md]]
28. SPEC-FIRST: Every module gets a Kiro spec (Requirements → Design → Tasks) BEFORE any code.
29. DEPTH-FIRST: One module complete (code + tests + passing) before the next starts. No scaffolding ahead.
30. INTEGRATION GATES: Phase boundary tests with real interfaces. No phase transition without passing.
31. TDD: Tests written WITH implementation. Each test references a spec acceptance criterion.
32. SECURITY PER MODULE: No credentials, inputs validated (Pydantic), MNPI filtered, audit logged, cost_basis never null.
33. CONTEXT RESETS: Fresh conversation per module. Steering file provides persistent context.
34. NO MOCKS AT BOUNDARIES: Integration tests use real module interfaces, not mocked ones.

### Build Order
Phase 0: M3 (18 types) + M5 (config templates)
Phase 1: M1 + M10 + M2/M4 + M6 (trust layer) → WEDGE PRODUCT ships here
Phase 2: M7 + M11-REST + M9 + M8 + M12 (intelligence layer) → RIA lighthouse
Phase 3: Smarsh + Execution + Onboarding + SOC 2 → BD onboarding
Phase 4: M11-BLPAPI + M11-gRPC + M13 + hybrid topology → Tier 2/5

DO NOT skip phases. Each depends on the previous.

### 006 vs 007 Distinction
- 006 uses OpenClaw as agent runtime. 007 uses Managed Agents/Strands.
- 006 uses Bedrock only. 007 abstracts LLM provider.
- 006 has no OPA. 007's compliance is 100% OPA/Rego.
- 006 writes to IR_Audit_Log__c. 007 writes to 3-tier WORM.
- 006 is a single-agent system. 007 is multi-agent (supervisor + 5 specialists).
- Files in 006 folder follow 006 rules. Files in 007 folder follow 007 rules. Never mix.

# IMPL-08: Build Infrastructure Setup

> Date: April 15, 2026
> Category: IMPLEMENTATION (how to build)
> Purpose: Documents the build infrastructure for 007 — steering, hooks, CI/CD, and how they coexist with 006

---

## 006 vs 007 Coexistence

006 and 007 share the same workspace but have completely separate build infrastructure.

| Aspect | 006 | 007 |
|--------|-----|-----|
| Steering | .kiro/steering/006-openclaw-fsi.md (fileMatch: 006/**) | .kiro/steering/007-fsi-interoperability.md (fileMatch: 007/**) |
| Steering (auto) | .kiro/steering/006-gap-remediation.md (auto, references 006 docs) | None (007 uses fileMatch only) |
| Pre-write hook | 006-architecture-alignment (checks OpenClaw, Bedrock-only, MCP protocol) | 007-architecture-alignment (checks module boundaries, trust layer, OPA) |
| Post-write hook | 006-gap-review (checks against 006 assessment) | 007-post-write-review (checks against 007 architecture) |
| Code standards | 006-code-standards (Apex, Python, TypeScript, OpenClaw) | 007-opa-compliance-review (Rego-specific) |
| Credential scan | 006-no-credentials (fileCreated in 006/**) | Covered by 007-architecture-alignment rule 5 |
| Post-task | 006-post-task-verify (checks against design doc) | Not needed yet (no spec tasks defined) |
| CI/CD | None (006 uses manual deploy) | .github/workflows/007-ci.yml (lint, schema validate, OPA test) |

### How Hooks Distinguish 006 vs 007

All preToolUse hooks check the file path first:
- 006 hook: "ONLY if the file being written is inside my-agent-project-006-openclaw-salesforce-aws/"
- 007 hook: "ONLY if the file being written is inside my-agent-project-007-fsi-interoperability/"
- Both respond "ACCESS GRANTED" for files outside their scope

This means both hooks fire on every write, but each only enforces rules for its own project.

### Architecture Rule Differences

| Rule | 006 | 007 |
|------|-----|-----|
| Agent runtime | OpenClaw ONLY | Managed Agents (cloud) / Strands (hybrid) |
| LLM | Bedrock ONLY (Sonnet 4.6 + Haiku 4.5) | Abstracted (Bedrock default, swappable) |
| Compliance | Inline code + Bedrock Guardrails | OPA/Rego ONLY (deterministic, not LLM) |
| Audit | IR_Audit_Log__c (Salesforce) | 3-tier WORM (Langfuse + S3 Object Lock + CRM) |
| Protocol | MCP (GET / + POST /tools/list + POST /tools/call) | MCP (same) + BLPAPI + gRPC + FIX |
| Modules | Skills + MCP servers (flat) | 13 modules with strict boundaries |
| Schema | SF custom objects (IR_*) | 18 canonical types (JSON Schema) |

---

## Files Created

| File | Type | Purpose |
|------|------|---------|
| .kiro/steering/007-fsi-interoperability.md | Steering | Architecture rules for 007 (fileMatch scoped) |
| .kiro/hooks/007-architecture-alignment.kiro.hook | Hook | Pre-write: module boundaries, trust layer, MNPI, credentials |
| .kiro/hooks/007-post-write-review.kiro.hook | Hook | Post-write: architecture compliance verification |
| .kiro/hooks/007-opa-compliance-review.kiro.hook | Hook | OPA/Rego file edit: fail-closed, WSP annotation, deterministic |
| .github/workflows/007-ci.yml | CI/CD | Lint (ruff, OPA), schema validation, OPA tests |

---
inclusion: auto
---

# 006 Gap Remediation Steering

## Source of Truth
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/006-design-vs-reality-assessment.md]]
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/design-doc.md]]

## Rules for Gap Remediation

1. Every change MUST address a specific PARTIAL, NOT DONE, or BROKEN verdict from the assessment.
2. Do NOT touch Phase 2 (MCP Servers) — all 8 tasks are DONE.
3. Do NOT touch Phase 6 (MuleSoft) — out of scope for this remediation.
4. All code must be reproducible: `sf project deploy start`, `sam deploy`, `npm run build`, `python test-pipeline.py` must all work after changes.
5. No credentials in code. All secrets via environment variables or AWS Secrets Manager.
6. Every agent action must write to IR_Audit_Log__c.
7. MNPI fields (holdings amounts, trade intentions, wire details) must NEVER be sent to LLM prompts.
8. Frontend connects to OpenClaw WebSocket only — no direct Salesforce API calls for agent queries.
9. OpenClaw is the ONLY agent runtime. No Agentforce, no Strands.
10. LLM is Bedrock only (Claude Sonnet 4.6 / Haiku 4.5). No OpenAI, no Comprehend, no FinBERT.

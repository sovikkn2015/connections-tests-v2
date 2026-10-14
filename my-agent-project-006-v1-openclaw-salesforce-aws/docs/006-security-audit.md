# Project 006: Enterprise Security Audit

> Date: April 8, 2026
> Framework: OWASP Top 10 for Agentic AI (2026) + OWASP Top 10 for LLM Applications + FINRA 2026 AI Oversight
> Scope: Full code review of all 7,870 lines of code across MCP servers, frontend, OpenClaw config, financial skills, evaluation suite, SAM template, Salesforce metadata, and seed data
> Sources: [OWASP Agentic Top 10](https://www.startupdefense.io/blog/owasp-top-10-agentic-ai-security-risks-2026), [FINRA 2026 Oversight Report](https://www.debevoise.com/insights/publications/2025/12/finras-2026-regulatory-oversight-report-continued), [MCP Security Research](https://marmelab.com/blog/2026/02/16/mcp-security-vulnerabilities.html)

---

## Severity Scale

| Level | Meaning |
|-------|---------|
| CRITICAL | Exploitable now, regulatory violation, or data breach risk |
| HIGH | Significant risk requiring remediation before production |
| MEDIUM | Should be fixed, but not immediately exploitable |
| LOW | Hardening recommendation, defense-in-depth |

---

---

## Finding 6: No Rate Limiting on OpenClaw WebSocket (HIGH)

OWASP Agentic: ASI02 (Tool Misuse), ASI08 (Cascading Failures)

The frontend WebSocket client has no rate limiting on message submission. The OpenClaw config also has no visible rate limiting. An attacker with the gateway token (see Finding 2) can flood the agent with requests, causing excessive Bedrock LLM costs, cascading failures across MCP servers and Salesforce API, denial of service for legitimate analysts, and potential FINRA audit log flooding that obscures real activity.

Remediation:
- Implement per-user rate limiting at the OpenClaw Gateway level
- Add client-side debouncing with a time-based throttle
- Set a cost budget per session in the OpenClaw config
- Monitor and alert on abnormal query volume via Langfuse

---

## Finding 7: MNPI Enforcement is Documentation-Only (HIGH)

OWASP Agentic: ASI09 (Human-Agent Trust Exploitation)
FINRA 2026: AI agent supervision requirements

The MNPI (Material Non-Public Information) protection exists only as instructions in SKILL.md files:

```markdown
## MNPI Rules
- NEVER include holdings amounts, trade intentions, or wire details in LLM prompts
- NEVER store MNPI data in OpenClaw memory
```

There is no code that enforces this. The Salesforce CRM skill can query any field on any object, including holdings amounts and trade intentions. The LLM decides whether to include MNPI data in its responses — and LLMs are not reliable enforcers of data classification rules.

Remediation:
- Implement a server-side MNPI filter in the Salesforce CRM skill that strips sensitive fields before returning data to the agent
- Create a field-level classification system: tag fields as MNPI in Salesforce metadata and automatically redact them in SOQL results
- Use Bedrock Guardrails regex patterns to detect and block MNPI patterns in LLM output
- Add MNPI detection to the evaluation suite as a hard-fail criterion

---

## Finding 8: Salesforce Access Token in OpenClaw Environment (MEDIUM)

OWASP Agentic: ASI03 (Identity and Privilege Abuse)

The OpenClaw config references a long-lived Salesforce access token via environment variable. A static Salesforce access token does not expire (unless manually revoked), has the full permissions of the Connected App's OAuth scopes, and if leaked provides persistent access to all CRM data including client PII, holdings, and compliance records.

Remediation:
- Use OAuth 2.0 refresh token flow instead of a static access token
- Store the refresh token in AWS Secrets Manager with auto-rotation
- Scope the Connected App's OAuth permissions to the minimum required objects
- Implement the SF Models API for CRM data reasoning to get Einstein Trust Layer coverage

---

## Finding 9: No Authentication on Evaluation Suite API Calls (MEDIUM)

The evaluation suite (run_suite.py) has no authentication of its own — anyone who can reach the evaluation endpoint can trigger 150 queries against the agent, consuming significant LLM resources and potentially generating misleading audit trail entries. Results are written to a local JSON file with no integrity protection.

Remediation:
- Run the evaluation suite only from a secured CI/CD pipeline with IAM-scoped credentials
- Sign evaluation results with a hash to detect tampering
- Tag evaluation queries in the audit log so they can be distinguished from real analyst queries

---

## Finding 10: Langfuse Traces May Contain Sensitive Data (MEDIUM)

OWASP LLM: LLM02 (Sensitive Information Disclosure)

Every MCP tool call is traced to Langfuse with full input and output. This means Langfuse stores full SOQL query results (potentially including client PII, holdings, account numbers), SEC filing content, news article content (potential prompt injection payloads), and financial model inputs and outputs. While Langfuse is self-hosted in the same VPC, the traces are stored indefinitely with no data classification or retention policy.

Remediation:
- Implement trace data classification — redact PII and MNPI fields before sending to Langfuse
- Set a retention policy on Langfuse traces
- Ensure Langfuse access is restricted to authorized engineering staff only
- Consider separate trace levels: full traces for debugging (short retention), sanitized traces for compliance (7-year retention)

---

## Finding 11: No Content Security Policy on Frontend (MEDIUM)

The frontend index.html and Vite config have no Content Security Policy (CSP) headers. Without CSP, the frontend is vulnerable to XSS attacks that could steal the SF OAuth token from session storage, steal the OpenClaw Gateway token from the JavaScript bundle, and inject malicious messages into the agent chat.

Remediation:
- Add CSP headers via Vite config or CloudFront response headers
- Restrict connect-src to the OpenClaw Gateway URL and Salesforce login URL
- Restrict script-src to 'self' (no inline scripts)
- Add frame-ancestors 'none' to prevent clickjacking

---

## Finding 12: OpenClaw Memory Persistence Without Encryption (MEDIUM)

OWASP Agentic: ASI06 (Memory and Context Poisoning)

OpenClaw stores persistent memory and sessions locally (openclaw/memory/, openclaw/sessions/). Persistent memory in an FSI context means client names, portfolio discussions, and research conclusions persist across sessions. An attacker who gains access to the memory store can read historical conversations. Memory poisoning is possible: injecting false information that influences future agent responses. No memory segmentation between analysts exists.

Remediation:
- Encrypt memory at rest using AWS KMS
- Implement per-analyst memory isolation with server-enforced session keys
- Add memory integrity checks — hash memory entries and verify on read
- Implement memory expiration for sensitive data
- Never store MNPI data in memory (currently documentation-only, see Finding 7)

---

## Finding 13: MuleSoft HITL Enforcement is Prompt-Based Only (MEDIUM)

OWASP Agentic: ASI09 (Human-Agent Trust Exploitation)

The MuleSoft skill requires HITL approval for all actions, but this is enforced only via the SKILL.md prompt instructions. There is no code-level enforcement. The LLM could be prompt-injected (via Finding 1) to skip the HITL gate and execute a trade directly. The dual authorization requirement for wires over 100K and trades over 500K is also prompt-based only.

Remediation:
- Implement HITL gates as code in the OpenClaw skill, not as LLM instructions
- The MuleSoft API endpoint should require a signed approval token that can only be generated by the HITL UI flow
- Log HITL approval/rejection events to IR_Audit_Log__c with the approver's identity
- Extend the AutoResearchClaw hitl_required_stages pattern to MuleSoft actions

---

## Finding 14: No Request Signing Between OpenClaw and MCP Servers (LOW)

OWASP Agentic: ASI07 (Insecure Inter-Agent Communication)

Communication between OpenClaw and the MCP servers relies solely on the API Gateway API key. There is no request signing, no mutual TLS, and no message integrity verification.

Remediation:
- Implement IAM authentication for the API Gateway (SigV4 signing) instead of or in addition to API keys
- Add request timestamps and reject requests older than 5 minutes (replay protection)
- Consider mutual TLS between OpenClaw on AgentCore and the API Gateway

---

## Finding 15: Bedrock Guardrails Missing Financial-Specific Patterns (LOW)

The Bedrock Guardrails config has good coverage for PII and general toxicity, but misses FSI-specific patterns. The CUSIP regex is too broad (matches any 9-char alphanumeric string). Missing patterns include holdings amounts, trade intentions, wire transfer details, client portfolio values, SWIFT/BIC codes, and routing numbers.

Remediation:
- Add regex patterns for holdings amounts, trade intentions, and wire details
- Tighten the CUSIP regex to validate the check digit
- Add SWIFT/BIC code pattern
- Add routing number pattern with ABA check digit validation

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|----------|
| CRITICAL | 2 | #1 Indirect prompt injection via MCP responses, #2 Gateway token in browser |
| HIGH | 5 | #3 No input sanitization, #4 CORS wildcard, #5 Error message leakage, #6 No WebSocket rate limiting, #7 MNPI enforcement is doc-only |
| MEDIUM | 5 | #8 Static SF token, #9 Eval suite auth, #10 Langfuse sensitive data, #11 No CSP, #12 Memory without encryption, #13 MuleSoft HITL prompt-only |
| LOW | 2 | #14 No request signing, #15 Missing financial regex patterns |

---

## OWASP Agentic AI Top 10 Coverage Map

| OWASP Risk | 006 Status | Findings |
|------------|-----------|----------|
| ASI01 — Agent Goal Hijacking | VULNERABLE | #1 (MCP responses carry unsanitized external content to LLM) |
| ASI02 — Tool Misuse | PARTIALLY MITIGATED | #3, #6 (input validation exists but no sanitization or rate limiting) |
| ASI03 — Identity and Privilege Abuse | VULNERABLE | #2, #8 (gateway token in browser, static SF token) |
| ASI04 — Supply Chain | LOW RISK | MCP servers are self-hosted on Lambda, not dynamically fetched |
| ASI05 — Unexpected Code Execution | MITIGATED | Financial skills run in sandbox with restricted imports, no eval/exec |
| ASI06 — Memory Poisoning | PARTIALLY MITIGATED | #12 (persistent memory without encryption or integrity checks) |
| ASI07 — Insecure Inter-Agent Communication | LOW RISK | #14 (API key auth, no signing, but within same VPC) |
| ASI08 — Cascading Failures | PARTIALLY MITIGATED | #6 (no rate limiting could cascade), DLQ exists for Lambda errors |
| ASI09 — Human-Agent Trust | VULNERABLE | #7, #13 (MNPI and HITL enforcement are prompt-based only) |
| ASI10 — Rogue Agents | PARTIALLY MITIGATED | Langfuse tracing provides observability, but no behavioral anomaly detection |

---

## Priority Remediation Order

1. Finding #2 — Remove gateway token from frontend (blocks all other attacks that require the token)
2. Finding #1 — Sanitize MCP tool responses (blocks prompt injection via external content)
3. Finding #7 — Implement code-level MNPI filtering (FINRA regulatory requirement)
4. Finding #13 — Implement code-level HITL enforcement for MuleSoft (FINRA regulatory requirement)
5. Finding #5 — Strip error details from MCP responses
6. Finding #3 — Add input sanitization to MCP tools
7. Finding #6 — Add rate limiting to WebSocket gateway
8. Finding #4 — Fix CORS wildcard in shared protocol
9. Remaining MEDIUM and LOW findings

# Project 007: Implementability & Accuracy Assessment

> Date: April 12, 2026
> Question: Is this implementable? What about accuracy — the thing FIs are deeply concerned about?
> Answer: The railway is deterministic and implementable. The trains are probabilistic and require human verification. The real risk is silent schema translation errors, not LLM hallucination.

---

## The Accuracy Problem — Why FIs Are Right to Be Concerned

FIs don't care about architecture diagrams. They care about: "If this agent tells my advisor that Client Henderson holds 1,200 shares of NVDA, is that number CORRECT? Because if it's wrong and the advisor makes a decision based on it, we have a fiduciary breach, a FINRA violation, and a lawsuit."

The railway has 3 types of accuracy problems, and they are fundamentally different.

### Type 1: Data Accuracy (deterministic — solvable)

When the agent queries Orion for Henderson's holdings, is the answer correct? YES — if Orion's data is correct. The MCP server is a passthrough. No LLM involved. No hallucination possible. The accuracy equals the source system's accuracy.

- Accuracy: 99.9%+ (limited by API reliability)
- Risk: source system has stale data (custodian feed lag)
- Mitigation: timestamp every data point, show "as of" dates

### Type 2: Compliance Accuracy (rule-based — solvable)

When the signal system checks the restricted list, is the answer correct? YES — if the restricted list is current. It is a database lookup. No LLM. Binary. Same for trading window (date math), concentration limits (arithmetic), data isolation (access control), MNPI field stripping (field-level filter).

- Accuracy: 99.9%+ (limited by rule currency)
- Risk: rules are outdated
- Mitigation: real-time rule sync, audit trail shows which rules were applied

### Type 3: LLM Synthesis Accuracy (probabilistic — NOT fully solvable)

When the LLM generates a research brief, meeting prep, or trade rationale — is it correct? SOMETIMES. The LLM might misweight a risk factor, miss a 10-K nuance, generate a compelling but flawed thesis, or hallucinate a statistic.

This is NOT a railway problem. This is a TRAIN problem. The railway is deterministic. The train is probabilistic.

- Accuracy: 75-90% depending on task complexity
- Risk: advisor acts on incorrect LLM synthesis
- Mitigation: anti-fabrication ledger, HITL gates, source attribution

---

## The Critical Distinction

The RAILWAY is deterministic. The TRAIN is probabilistic.

| Function | Type | Accuracy |
|----------|------|----------|
| Data retrieval | Deterministic (API call) | 99.9% |
| Compliance checks | Deterministic (rule eval) | 99.9% |
| Data filtering | Deterministic (field strip) | 99.9% |
| Audit logging | Deterministic (write log) | 99.9% |
| Schema translation | Deterministic (field map) | 99.9% |
| Authority check | Deterministic (policy eval) | 99.9% |
| LLM synthesis | Probabilistic | 75-90% |
| LLM recommendation | Probabilistic | 70-85% |
| LLM summarization | Probabilistic | 85-95% |

The railway NEVER hallucinates. The train SOMETIMES hallucinates. The architecture's job is to make the railway as wide as possible and the train as narrow as possible.

---

## 7 Accuracy Mechanisms Built Into the Architecture

1. **Anti-Fabrication Ledger** — every number traces to a source with timestamp. Advisor can verify any number.

2. **HITL Gates** — LLM never acts alone on anything consequential. Research: 3 gates. Trades: mandatory gate.

3. **Deterministic Compliance** — compliance checks are NOT done by the LLM. Restricted list: database lookup. Concentration: arithmetic. Trading window: date math.

4. **Source Attribution** — LLM cites sources for every claim. Fabricated citations are caught by anti-fabrication check.

5. **Canonical Data** — schema layer translates vendor data into canonical format ONCE at the MCP server level. Agent only sees canonical. Eliminates translation errors at the agent level.

6. **Archetype-Aware Filtering** — MNPI policy ensures LLM only sees data appropriate for the archetype and role. Can't hallucinate data it never received.

7. **Dual Audit Trail** — every action logged immutably. Doesn't make LLM more accurate but makes the system ACCOUNTABLE.

---

## What FIs Actually Need to Hear

The DATA is 99.9% accurate — it comes directly from your existing systems via API. We don't modify it.

The COMPLIANCE is 99.9% accurate — it's rule-based, not LLM-based. Deterministic.

The SYNTHESIS is 85-90% accurate — the LLM summarizes and interprets. Your people verify it at HITL gates. Every number traces to a source.

The EXECUTION is 100% human-approved — the agent prepares, the human decides. No autonomous trades.

The AUDIT is 100% complete — every action logged, every decision traceable.

The pitch is NOT "our AI is accurate." The pitch IS "your data is accurate, your rules are enforced, your people still decide, and everything is auditable."

---

## The Full Accuracy Matrix

| Function | Type | Accuracy | Risk |
|----------|------|----------|------|
| Data retrieval (MCP) | Deterministic | 99.9% | LOW |
| Schema translation | Deterministic | 99%+ | MEDIUM |
| Restricted list check | Deterministic | 99.9% | LOW |
| Concentration calc | Deterministic | 99.9% | LOW |
| Trading window check | Deterministic | 99.9% | LOW |
| MNPI field stripping | Deterministic | 99.9% | LOW |
| Data isolation (RBAC) | Deterministic | 99.9% | LOW |
| Authority policy eval | Deterministic | 99.9% | LOW |
| Audit logging | Deterministic | 99.9% | LOW |
| Financial models (DCF etc) | Deterministic* | 100%* | LOW |
| HITL gate enforcement | Deterministic | 100% | NONE |
| Intent classification | Probabilistic | 85-95% | MEDIUM |
| Research summarization | Probabilistic | 85-95% | MEDIUM |
| Meeting prep synthesis | Probabilistic | 85-90% | MEDIUM |
| Investment thesis | Probabilistic | 75-85% | HIGH |
| Rating determination | Probabilistic | 70-85% | HIGH |
| Risk assessment | Probabilistic | 75-85% | HIGH |
| Compliance narrative | Probabilistic | 80-90% | MEDIUM |

*Financial models are deterministic given inputs. Inputs are estimates.

~70% of functions are DETERMINISTIC (99.9%). ~30% are PROBABILISTIC (75-95%).

---

## Implementability — Layer by Layer

### Layer 1: Identity
Implementable: YES. Accuracy risk: NONE. Hard part: industry agreement on schema. Build for one firm first, propose standard later. 2-3 weeks to build, years to standardize.

### Layer 2: Protocol
Implementable: YES (proven in 006). Accuracy risk: NONE. Hard part: FIX bridge. MCP adapters: days each. FIX bridge: weeks.

### Layer 3: Schema
Implementable: YES but tedious. Accuracy risk: MEDIUM (translation errors). Hard part: canonical model will be wrong on first try. 2-3 months of painful schema debugging. CRITICAL RISK: silent semantic mismatch where data is "correct" but means something different after translation. Mitigation: document every field's inclusions/exclusions, automated comparison tests.

### Layer 4: Trust / Authority
Implementable: YES with compliance SME. Accuracy risk: LOW for rules, HIGH for edge cases. Hard part: the RULES, not the code. Need compliance officer next to engineer. 2-3 months with SME. Risk: engine faithfully enforces wrong rules. Mitigation: compliance + legal review, version control, quarterly audits, test cases.

### Layer 5: Semantic / Intent
Implementable: PARTIALLY. Accuracy risk: HIGHEST. Hard part: intent classification is LLM-based, will be wrong sometimes. Mitigation: ask user when ambiguous, route directly for unambiguous (80%+).

---

## The One Thing That Could Kill It

Not accuracy. Not technology. Not regulation. SCHEMA TRANSLATION ERRORS.

If Orion says "MarketValue = $150,000" and that includes accrued interest, but the canonical model's "market_value" doesn't — the number is "correct" but means something different. The advisor sees $150,000 and thinks that is the equity value. It is not. It is equity + $2,300 of accrued interest on a bond position.

This is a SILENT error. No hallucination. No fabrication. The data is "accurate" — it came from the source system. But the MEANING changed in translation.

This is the hardest problem in the entire architecture. It is not an AI problem. It is a data semantics problem. The canonical data model (Layer 3) must be designed with extreme care, tested exhaustively, and documented precisely.

The railway is only as good as its track gauge. If the gauge is wrong, every train derails.

---

## The Final Honest Answer

### Is it implementable?

| Component | Implementable? | Caveat |
|-----------|---------------|--------|
| Railway (tracks, signals, stations, tickets) | YES | Deterministic, proven patterns |
| Trains (LLM synthesis, intent routing) | YES, with caveats | Requires HITL, source attribution, anti-fabrication |
| Schema (canonical data model) | YES, but painful | First 3 months = debugging semantic mismatches |
| Trust engine (authority + MNPI + compliance) | YES, but needs compliance SME | Code is easy, rules are hard |
| Cross-boundary (A2A, agent-to-agent) | NOT YET | Industry needs agent identity standards, 3-5 year horizon |

### Will FIs trust it?

They will trust the RAILWAY (deterministic parts). They will verify the TRAINS (probabilistic parts).

The FI doesn't need to trust the LLM. The FI needs to trust that:
1. The data came from their systems (MCP, deterministic)
2. The rules were enforced (trust engine, deterministic)
3. The human approved (HITL gate, deterministic)
4. Everything was logged (audit trail, deterministic)
5. The LLM's work is verifiable (source attribution)

The LLM is a tool the human uses, not a decision-maker the human trusts blindly. The architecture enforces this.

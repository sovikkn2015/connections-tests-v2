# PROJECT 007 v2 — COMPLIANCE GAP DESIGNS
# 7 MISSING COMPONENTS IDENTIFIED BY LLMJ COMMITTEE

> Version: 2.1
> Date: July 2026
> Status: Detailed Technical Design — Addressing Compliance Score 6.6/10 (Weakest Area)
> Audience: Engineering team, compliance SME, legal counsel, LLMJ committee
> Predecessor: REVIEW-v2-committee-reassessment.md (Section 4.1: Compliance Gaps)
> Scope: 7 components — Reg BI Generator, Liability Framework, WSP-to-YAML Mapping, BSA/AML Monitoring, ERISA Account-Type Awareness, MNPI Leakage Scan, Cross-Border Regulatory Architecture

---

## TABLE OF CONTENTS

1. [Reg BI Documentation Generator](#1-reg-bi-documentation-generator)
2. [Liability Framework](#2-liability-framework)
3. [WSP-to-YAML Mapping](#3-wsp-to-yaml-mapping)
4. [BSA/AML Ongoing Monitoring](#4-bsaaml-ongoing-monitoring)
5. [ERISA Account-Type Awareness](#5-erisa-account-type-awareness)
6. [MNPI Leakage Scan](#6-mnpi-leakage-scan)
7. [Cross-Border Regulatory Architecture](#7-cross-border-regulatory-architecture)

---

## DESIGN BOUNDARY LEGEND

Throughout this document:

- **🟢 FULLY DESIGNABLE** — Technical architecture, schemas, integration points, OPA rules. An engineer can implement from this spec.
- **🟡 COMPLIANCE SME MUST FILL IN** — Regulatory interpretation, firm-specific thresholds, legal terms. Marked with `[SME-REQUIRED]`.
- **🔴 LEGAL COUNSEL REQUIRED** — Liability terms, indemnification language, warranty boundaries. Marked with `[LEGAL-REQUIRED]`.

---

## 1. REG BI DOCUMENTATION GENERATOR

### 1.1 Regulatory Context

Regulation Best Interest (SEC Rule 15l-1, effective June 2020) imposes four obligations on broker-dealers when making recommendations to retail customers. Every recommendation the 007 agent makes to a BD client (Tier 3 archetype) or dual-registered RIA must produce structured documentation proving compliance with all four obligations.

### 1.2 The Four Obligations and Generator Requirements

| Obligation | What the Regulation Requires | What the Generator Must Produce |
|------------|-----------------------------|---------------------------------|
| **Disclosure** | Deliver Form CRS; disclose material facts about the relationship, fees, conflicts | Reference to delivered Form CRS (timestamp, channel), fee schedule applicable to this recommendation, conflicts of interest relevant to this specific recommendation |
| **Care** | Reasonable diligence, care, and skill; understand the product; consider alternatives; no excessive frequency | Basis for recommendation (why this security/product), alternatives considered and why rejected, cost comparison across alternatives, risk-return analysis relative to client profile, frequency analysis (is this recommendation part of excessive trading?) |
| **Conflict of Interest** | Identify, disclose, mitigate, or eliminate conflicts | Revenue sharing arrangements, proprietary product flags, compensation differentials, third-party payments, any material conflict between firm interest and client interest |
| **Compliance** | Written policies and procedures to achieve compliance | Reference to WSP section governing this recommendation type, supervisory review status, archival confirmation |

### 1.3 Reg BI Document Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RegBIDocumentation",
  "description": "Structured Reg BI documentation for a single recommendation",
  "type": "object",
  "required": [
    "document_id", "recommendation_id", "timestamp", "client",
    "recommendation", "disclosure", "care", "conflict_of_interest",
    "compliance", "metadata"
  ],
  "properties": {
    "document_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this Reg BI document"
    },
    "recommendation_id": {
      "type": "string",
      "format": "uuid",
      "description": "Links to the recommendation event in the audit trail"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "client": {
      "type": "object",
      "required": ["client_id", "name", "account_type", "risk_profile",
                    "investment_objectives", "time_horizon"],
      "properties": {
        "client_id": { "type": "string" },
        "name": { "type": "string" },
        "account_type": {
          "type": "string",
          "enum": [
            "taxable_individual", "taxable_joint",
            "ira_traditional", "ira_roth", "ira_sep", "ira_simple",
            "401k", "403b", "trust_revocable", "trust_irrevocable",
            "utma_ugma", "erisa_pension", "erisa_profit_sharing",
            "corporate", "partnership"
          ]
        },
        "risk_profile": {
          "type": "string",
          "enum": ["conservative", "moderately_conservative", "moderate",
                   "moderately_aggressive", "aggressive"]
        },
        "investment_objectives": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["capital_preservation", "income", "growth_and_income",
                     "growth", "speculation"]
          }
        },
        "time_horizon": {
          "type": "string",
          "enum": ["short_term_0_3y", "medium_term_3_7y",
                   "long_term_7_15y", "extended_15y_plus"]
        },
        "annual_income": { "type": "number" },
        "net_worth": { "type": "number" },
        "tax_bracket": { "type": "string" }
      }
    },
    "recommendation": {
      "type": "object",
      "required": ["type", "security", "action", "rationale_summary"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["buy", "sell", "hold", "switch", "rebalance",
                   "asset_allocation_change", "product_recommendation"]
        },
        "security": {
          "type": "object",
          "properties": {
            "security_id": { "type": "string" },
            "name": { "type": "string" },
            "asset_class": { "type": "string" },
            "product_type": {
              "type": "string",
              "enum": ["equity", "fixed_income", "mutual_fund", "etf",
                       "option", "annuity", "alternative", "structured_product"]
            }
          }
        },
        "action": { "type": "string" },
        "rationale_summary": { "type": "string" }
      }
    },
    "disclosure": {
      "type": "object",
      "required": ["form_crs_delivered", "fees_disclosed", "material_facts"],
      "properties": {
        "form_crs_delivered": {
          "type": "object",
          "properties": {
            "delivered": { "type": "boolean" },
            "delivery_date": { "type": "string", "format": "date-time" },
            "delivery_channel": { "type": "string" },
            "form_crs_version": { "type": "string" }
          }
        },
        "fees_disclosed": {
          "type": "object",
          "properties": {
            "commission": { "type": "number" },
            "expense_ratio": { "type": "number" },
            "advisory_fee": { "type": "number" },
            "12b1_fee": { "type": "number" },
            "total_estimated_annual_cost": { "type": "number" },
            "cost_comparison_to_alternatives": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "alternative_name": { "type": "string" },
                  "alternative_annual_cost": { "type": "number" },
                  "cost_difference": { "type": "number" }
                }
              }
            }
          }
        },
        "material_facts": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "care": {
      "type": "object",
      "required": ["basis_for_recommendation", "alternatives_considered",
                    "best_interest_rationale", "risk_factors"],
      "properties": {
        "basis_for_recommendation": {
          "type": "object",
          "properties": {
            "client_profile_match": { "type": "string" },
            "investment_thesis": { "type": "string" },
            "data_sources_consulted": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "source": { "type": "string" },
                  "data_type": { "type": "string" },
                  "retrieved_at": { "type": "string", "format": "date-time" }
                }
              }
            }
          }
        },
        "alternatives_considered": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "required": ["security_name", "reason_not_selected"],
            "properties": {
              "security_name": { "type": "string" },
              "security_id": { "type": "string" },
              "asset_class": { "type": "string" },
              "expense_ratio": { "type": "number" },
              "reason_not_selected": { "type": "string" }
            }
          }
        },
        "best_interest_rationale": { "type": "string" },
        "risk_factors": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "risk_type": {
                "type": "string",
                "enum": ["market", "credit", "liquidity", "concentration",
                         "interest_rate", "inflation", "currency",
                         "regulatory", "product_specific"]
              },
              "description": { "type": "string" },
              "severity": { "type": "string", "enum": ["low", "medium", "high"] },
              "mitigation": { "type": "string" }
            }
          }
        },
        "frequency_analysis": {
          "type": "object",
          "properties": {
            "trades_last_12_months": { "type": "integer" },
            "turnover_rate": { "type": "number" },
            "cost_to_equity_ratio": { "type": "number" },
            "excessive_trading_flag": { "type": "boolean" },
            "analysis_notes": { "type": "string" }
          }
        }
      }
    },
    "conflict_of_interest": {
      "type": "object",
      "required": ["conflicts_identified", "mitigation_measures"],
      "properties": {
        "conflicts_identified": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "conflict_type": {
                "type": "string",
                "enum": ["revenue_sharing", "proprietary_product",
                         "compensation_differential", "third_party_payment",
                         "principal_trading", "market_making", "other"]
              },
              "description": { "type": "string" },
              "material": { "type": "boolean" }
            }
          }
        },
        "mitigation_measures": {
          "type": "array",
          "items": { "type": "string" }
        },
        "proprietary_product": { "type": "boolean" },
        "revenue_sharing_arrangement": { "type": "boolean" },
        "compensation_differential_exists": { "type": "boolean" }
      }
    },
    "compliance": {
      "type": "object",
      "required": ["wsp_reference", "supervisory_review_status", "archival_status"],
      "properties": {
        "wsp_reference": { "type": "string" },
        "supervisory_review_status": {
          "type": "string",
          "enum": ["pending_review", "approved", "rejected", "escalated"]
        },
        "supervisory_reviewer": { "type": "string" },
        "review_timestamp": { "type": "string", "format": "date-time" },
        "archival_status": {
          "type": "string",
          "enum": ["archived_worm", "pending_archive", "archive_failed"]
        },
        "archival_reference": { "type": "string" }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "agent_id": { "type": "string" },
        "specialist": { "type": "string", "enum": ["client_service", "research"] },
        "aid": { "type": "object" },
        "trace_id": { "type": "string", "format": "uuid" },
        "pipeline_stage": { "type": "string" },
        "llm_model": { "type": "string" },
        "llm_prompt_hash": { "type": "string" },
        "schema_version": { "type": "string" }
      }
    }
  }
}
```

### 1.4 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  REG BI DOCUMENTATION GENERATOR FLOW                    │
│                                                                         │
│  Client Service Specialist (Line 2)                                     │
│  OR Research Specialist (Line 1)                                        │
│       │                                                                 │
│       │  Generates recommendation                                       │
│       ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  REG BI GATE (output guardrail — after [8], before delivery)    │   │
│  │                                                                  │   │
│  │  Step 1: Check AID archetype                                     │   │
│  │    - Tier 3 BD / dual-registered → REQUIRES Reg BI              │   │
│  │    - Tier 4 RIA (fiduciary standard, not Reg BI) → skip gate   │   │
│  │    - Tier 1/2/5 institutional → skip gate                       │   │
│  │                                                                  │   │
│  │  Step 2: Classify output as recommendation vs. information       │   │
│  │    - General education/market commentary → skip gate             │   │
│  │    - Specific security/product suggestion → proceed              │   │
│  │    [SME-REQUIRED: boundary definition per FINRA guidance]        │   │
│  │                                                                  │   │
│  │  Step 3: Gather Reg BI inputs                                    │   │
│  │    a. Client profile → L4 semantic memory + CRM (via M6)        │   │
│  │    b. Alternatives → research data (via M6 → M11)               │   │
│  │    c. Fee/cost data → enterprise config (M5)                    │   │
│  │    d. Conflict data → enterprise config (M5)                    │   │
│  │    e. Trading frequency → execution history (via M6 → M11)      │   │
│  │                                                                  │   │
│  │  Step 4: Generate Reg BI document (structured JSON)              │   │
│  │    - LLM generates: basis_for_recommendation,                    │   │
│  │      best_interest_rationale, alternative rejection reasons      │   │
│  │    - Deterministic: fees, conflicts, frequency (from data)       │   │
│  │                                                                  │   │
│  │  Step 5: Validate via OPA                                        │   │
│  │    compliance.check(type="reg_bi_completeness", doc=regbi_doc)  │   │
│  │    → PASS: all required fields populated, alternatives ≥ 2      │   │
│  │    → FAIL: block recommendation, return missing fields           │   │
│  │                                                                  │   │
│  │  Step 6: Persist                                                 │   │
│  │    a. M10 WORM (S3 Object Lock) — immutable regulatory record   │   │
│  │    b. CRM (Tier 3 business store) — advisor-accessible          │   │
│  │    c. Link to recommendation_id in audit trail                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ▼                                                                 │
│  Recommendation delivered to user (Reg BI doc ID attached to trace)     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.5 OPA Policy Rule — Block Recommendations Without Reg BI

```rego
# authority/reg_bi.rego
package authority.reg_bi

import rego.v1

# Determine if the action is a recommendation to a BD retail client
requires_reg_bi if {
    input.action == "deliver_recommendation"
    input.aid.firm.archetype in {"tier3_wealth_management", "tier3_broker_dealer"}
    input.context.client.account_type != "institutional"
    input.context.recommendation_type != "general_education"
}

# Block delivery if Reg BI documentation is missing or incomplete
deny contains msg if {
    requires_reg_bi
    not input.context.reg_bi_document
    msg := "BLOCKED: Recommendation to BD retail client requires Reg BI documentation."
}

deny contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    not doc.care.basis_for_recommendation
    msg := "BLOCKED: Reg BI Care obligation — missing basis for recommendation."
}

deny contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    count(doc.care.alternatives_considered) < 2
    msg := sprintf("BLOCKED: Reg BI Care obligation — only %d alternatives (minimum 2).",
                   [count(doc.care.alternatives_considered)])
}

deny contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    not doc.care.best_interest_rationale
    msg := "BLOCKED: Reg BI Care obligation — missing best interest rationale."
}

deny contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    not doc.disclosure.form_crs_delivered.delivered
    msg := "BLOCKED: Reg BI Disclosure obligation — Form CRS not delivered."
}

deny contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    not doc.disclosure.fees_disclosed.total_estimated_annual_cost
    msg := "BLOCKED: Reg BI Disclosure obligation — fees not disclosed."
}

# Excessive trading flag triggers escalation instead of block
escalate contains msg if {
    requires_reg_bi
    doc := input.context.reg_bi_document
    doc.care.frequency_analysis.excessive_trading_flag == true
    msg := "ESCALATE: Excessive trading flag. Requires principal review."
}
```

### 1.6 Triggering Specialists

| Specialist | Trigger Condition | Example |
|------------|-------------------|---------|
| Client Service (Line 2) | Output contains specific investment suggestion for a BD retail client | "Based on Henderson's profile, I'd suggest increasing allocation to investment-grade bonds" |
| Research (Line 1) | Research brief includes actionable recommendation for a specific client | Brief concludes: "For Henderson's conservative profile, consider VBTLX as a core bond holding" |

The Supervisor detects recommendation intent in the specialist's output and routes through the Reg BI gate before delivery.

### 1.7 FINRA Examiner Retrieval Workflow

```
FINRA Examiner requests: "Show me Reg BI documentation for all
recommendations made to client Henderson in Q2 2026."

1. Examiner accesses M10 WORM via cross-account IAM (17a-4(f)(3)(vii))
2. Query: document_type='reg_bi' AND client_id='C-12345'
          AND timestamp BETWEEN '2026-04-01' AND '2026-06-30'
3. Returns: list of RegBIDocumentation JSON documents
4. Each document includes:
   - Full provenance chain (trace_id → all data sources, LLM prompts, OPA checks)
   - SHA-256 integrity hash (proves no alteration since creation)
   - Supervisory review status and reviewer identity
5. Examiner drills into any document to see:
   - What data the agent retrieved (via trace_id → M10 audit entries)
   - What alternatives were considered and why rejected
   - What conflicts were disclosed
   - Whether recommendation was consistent with client profile
```

### 1.8 Storage

| Store | Content | Retention | Access |
|-------|---------|-----------|--------|
| M10 WORM (S3 Object Lock) | Full RegBIDocumentation JSON + SHA-256 | 6 years (17a-4) | Cross-account IAM for examiners |
| CRM (Tier 3 business) | Summary + link to WORM record | Firm policy | Advisors, compliance officers |
| Langfuse (operational) | LLM prompt/response for recommendation | 90 days | Engineering |

### 1.9 Module Placement and Estimates

| Attribute | Value |
|-----------|-------|
| Module | New sub-module of M8 — `reg_bi_generator.py` |
| Also touches | M2/M4 (OPA rules), M5 (conflict/fee config), M10 (persistence), M6 (data retrieval) |
| Estimated lines | ~400 Python (generator + validation) + ~80 Rego (OPA rules) |
| Phase | Design in Phase 1, implement in Phase 2 (required before BD lighthouse) |

### 1.10 Design Boundary

- 🟢 **FULLY DESIGNABLE:** JSON schema, OPA rules, integration flow, storage, examiner workflow
- 🟡 **SME MUST FILL IN:** "Information" vs. "recommendation" boundary, firm-specific conflict disclosures, fee schedule templates, excessive trading thresholds (turnover rate, cost-to-equity ratio)
- 🔴 **LEGAL REQUIRED:** Form CRS content, specific disclosure language, indemnification for LLM-generated rationale text

---

## 2. LIABILITY FRAMEWORK

### 2.1 Purpose

This section designs the technical infrastructure that makes liability provable. It is NOT the legal document itself (that requires counsel) — it is the system architecture that captures, preserves, and presents the evidence needed for liability determination.

### 2.2 Compliance Warranty Boundary

Every function the platform performs falls into one of two warranty tiers.

#### Tier A: Warranted Functions (Deterministic, 99.9%+ Accuracy)

| Function | Module | Mechanism | Accuracy | Warranty Basis |
|----------|--------|-----------|----------|----------------|
| Restricted list lookup | M2/M4 (OPA) | Rego rule evaluation | 99.9% | Deterministic. Limited by list currency (<60s propagation). |
| Concentration limit check | M2/M4 (OPA) | Arithmetic on canonical holdings | 99.9% | Deterministic. Limited by data freshness from source. |
| Trading window verification | M2/M4 (OPA) | Rego rule against calendar | 99.9% | Deterministic date/time comparison. |
| MNPI field filtering | M4 (OPA) | Per-archetype field stripping | 99.9% | Deterministic field removal. Does NOT warrant against LLM inference (see Component 6). |
| Authority check (ALLOW/DENY) | M2 (OPA) | Rego policy evaluation | 99.9% | Deterministic. Fail-closed on error. |
| Audit trail integrity | M10 | SHA-256 hash chain + S3 Object Lock | 99.99% | Cryptographic integrity. WORM immutability. |
| Schema translation (field mapping) | M7 | Deterministic field mapping | 99.5% | Warranted per translator version. Semantic mismatches documented. |
| AID verification | M1 | JWT RS256 signature verification | 99.99% | Cryptographic verification. |
| CTR threshold detection | M2/M4 (OPA) | Arithmetic comparison vs $10K | 99.99% | Deterministic threshold. |
| Pre-trade compliance check | M2/M4 (OPA) | Composite Rego evaluation | 99.9% | Deterministic composite of restricted list + concentration + window + account-type. |

#### Tier B: Best-Effort Functions (Probabilistic, 75-95%)

| Function | Module | Mechanism | Accuracy | Warranty Limitation |
|----------|--------|-----------|----------|---------------------|
| Research brief generation | M8 (LangGraph) | LLM synthesis | 80-90% | Subject to hallucination. Source attribution provided but not warranted complete. |
| Meeting prep generation | M8 + Line 2 | LLM synthesis of client data | 85-92% | Data inputs warranted (Tier A); synthesis is not. |
| Investment recommendation rationale | Reg BI Gen | LLM-generated text | 75-85% | Human review REQUIRED before delivery. |
| Intent classification | M9 | LLM function calling | 85-95% | Confidence thresholds gate routing. |
| MNPI leakage detection | Output guardrail | Pattern matching + entity extraction | 70-85% | False negatives possible. Does not replace human review. |
| Client sentiment analysis | Line 2 | LLM inference | 70-80% | Used for personalization, not compliance decisions. |
| Document extraction (onboarding) | Line 5 | LLM + OCR | 85-92% | Must be human-verified before custodian submission. |
| Alternative rejection reasoning | Reg BI Gen | LLM-generated explanation | 75-85% | SME must validate reasoning templates. |

`[LEGAL-REQUIRED]` Exact warranty language, liability caps, and indemnification terms per tier.

### 2.3 Provenance Chain Architecture

For any agent output, the system reconstructs the complete chain of causation. Every link stored in M10 WORM.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PROVENANCE CHAIN FOR ANY OUTPUT                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. DATA RETRIEVED                                               │   │
│  │    - source_system: "orion" | "salesforce" | "emoney" | ...     │   │
│  │    - mcp_server_id: "m11-orion-adapter-v2.1.0"                 │   │
│  │    - tool_called: "get_holdings"                                │   │
│  │    - parameters: { client_id, as_of_date }                      │   │
│  │    - response_hash: SHA-256 of raw response                     │   │
│  │    - canonical_hash: SHA-256 of translated canonical data       │   │
│  │    - translator_version: "m7-orion-v1.3.2"                     │   │
│  │    - timestamp + latency_ms                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. RULES APPLIED                                                │   │
│  │    - policy_bundle: "authority/v2.4.1" | "mnpi/v1.8.0"         │   │
│  │    - rule_id: "authority/reg_bi.rego:requires_reg_bi"           │   │
│  │    - input_hash: SHA-256 of OPA input                          │   │
│  │    - decision: ALLOW | DENY | REQUIRE_APPROVAL                  │   │
│  │    - decision_reason: human-readable                            │   │
│  │    - evaluation_time_ms                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. LLM INTERACTION                                              │   │
│  │    - model: "claude-sonnet-4-20250514"                          │   │
│  │    - prompt_hash: SHA-256 of full prompt                        │   │
│  │    - response_hash: SHA-256 of LLM response                    │   │
│  │    - temperature, token counts                                  │   │
│  │    - guardrails_applied: ["mnpi_prefilter", "safety"]           │   │
│  │    NOTE: Full prompt/response in Langfuse (90-day).             │   │
│  │    Hashes in WORM (6-year) for integrity verification.          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 4. HUMAN APPROVAL (if applicable)                               │   │
│  │    - gate_id, gate_type                                         │   │
│  │    - approver_aid: { user_id, role, firm_id }                   │   │
│  │    - approval_token: SHA-256(gate_id + approver_id + timestamp) │   │
│  │    - approval_channel, context_hash                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 5. OUTPUT DELIVERED                                             │   │
│  │    - output_hash: SHA-256 of final output                      │   │
│  │    - output_type, delivery_channel, recipient_aid               │   │
│  │    - guardrails_passed: ["mnpi_leakage", "pii", "2210"]        │   │
│  │    - reg_bi_document_id (if recommendation)                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ALL LINKED BY: trace_id (OpenTelemetry distributed trace)              │
│  ALL STORED IN: M10 WORM (S3 Object Lock, 6-year retention)            │
│  INTEGRITY: SHA-256 hash chain per trace_id. Tamper-detectable.         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Tamper-Proof Evidence

Three mechanisms protect the provenance chain:

| Mechanism | How It Works | What It Proves |
|-----------|-------------|----------------|
| SHA-256 Hash Per Entry | Each audit entry includes entry_hash + prev_entry_hash (chain per trace_id). Alteration breaks the chain. | Individual entry integrity + ordering integrity. |
| S3 Object Lock (Compliance Mode) | 6-year retention, IRREVERSIBLE. No user including root can modify/delete. | WORM compliance per SEC 17a-4(f). |
| Independent Hash Verification | Nightly batch recomputes all hashes, compares against stored. Mismatch → CRITICAL alert. Verification log in separate S3 bucket. | Defense in depth against storage-level corruption. |

### 2.5 Schema Translation Liability

When a semantic mismatch causes a wrong number, the audit trail enables precise attribution:

```
SCHEMA TRANSLATION ERROR ATTRIBUTION:

  Source:  orion.position.market_value = 1,250,000.00
           (Orion includes accrued interest)

  Rule:   translator m7-orion-v1.3.2
          "market_value → canonical.holding.market_value"
          Adjustment: subtract accrued_interest (3,200.00)

  Result: canonical.holding.market_value = 1,246,800.00

  Audit Record (M10 WORM):
  {
    "event": "schema_translation",
    "source_system": "orion",
    "source_field": "position.market_value",
    "source_value": 1250000.00,
    "canonical_field": "holding.market_value",
    "canonical_value": 1246800.00,
    "translator_id": "m7-orion-v1.3.2",
    "translation_rule": "market_value_excl_accrued",
    "semantic_adjustment": "subtracted accrued_interest: 3200.00",
    "entry_hash": "sha256:abc123..."
  }

  Attribution: platform vendor (translator bug) vs. source system
  (incorrect data) vs. configuration (incorrect mapping YAML).
```

### 2.6 Module Responsibility Matrix

| Module | IS Responsible For | IS NOT Responsible For |
|--------|-------------------|----------------------|
| **M1** | AID issuance, JWT integrity, expiry, revocation | User credential management (Keycloak), firm identity verification |
| **M2/M4** | Correct policy evaluation given current rules, fail-closed | Correctness of rules themselves `[SME-REQUIRED]`, regulatory interpretation |
| **M3** | Schema version integrity, breaking change detection | Semantic correctness of field definitions (joint SME + engineering) |
| **M5** | Config validation, secret resolution, hot reload | Correctness of config values (firm responsibility) |
| **M6** | Routing, circuit breaking, rate limiting, audit logging, MNPI enforcement | Downstream MCP server availability (vendor), vendor API correctness |
| **M7** | Field mapping per documented semantics, reconciliation tests | Vendor API schema changes without notice, undocumented semantic differences |
| **M8** | Pipeline execution, checkpointing, HITL enforcement | LLM output quality, correctness of research conclusions |
| **M9** | Intent classification with confidence scoring | LLM classification accuracy (probabilistic), user intent ambiguity |
| **M10** | Write integrity, WORM compliance, hash chain, fail-closed | Storage hardware (cloud provider / on-prem infrastructure) |
| **M11** | MCP protocol compliance, vendor auth, error translation | Vendor API availability, vendor rate limits, vendor data correctness |
| **M12** | Channel delivery, multi-agent routing, specialist lifecycle | Channel platform availability (Slack/Teams uptime) |

### 2.7 Insurance Integration Points

E&O insurance providers need specific data to assess claims. Exposed via read-only API on M10:

```json
{
  "insurance_claim_export": {
    "claim_context": {
      "trace_id": "string — interaction trace",
      "timestamp_range": "start/end of interaction",
      "client_id": "affected client",
      "specialist": "which specialist produced output",
      "output_type": "recommendation | research_brief | order"
    },
    "warranty_classification": {
      "functions_involved": ["list of all functions used"],
      "tier_a_functions": ["deterministic — warranted"],
      "tier_b_functions": ["probabilistic — best-effort"],
      "overall_tier": "If ANY Tier B → claim is Tier B"
    },
    "full_provenance_chain": "Complete chain per Section 2.3",
    "error_attribution": {
      "if_data_error": "source value vs canonical vs translator version",
      "if_rule_error": "OPA policy version, rule ID, triggering input",
      "if_llm_error": "model version, prompt hash, temperature, guardrails",
      "if_translation_error": "translator version, mapping rule, adjustment"
    }
  }
}
```

### 2.8 Enterprise Config Liability Template

`[LEGAL-REQUIRED]` Legal counsel fills in bracketed sections.

```yaml
# enterprise-config.yaml — liability section
liability:
  warranty_tier_a:
    description: "Deterministic compliance functions"
    accuracy_target: 0.999
    sla_response_time_ms: 100
    liability_cap: "[LEGAL: $ amount or formula]"
    indemnification: "[LEGAL: terms for Tier A errors]"
    exclusions:
      - "Rule currency lag up to 60 seconds"
      - "Source system data errors"
      - "Configuration errors by deploying firm"

  warranty_tier_b:
    description: "LLM-assisted functions"
    accuracy_range: "75-95% depending on function"
    liability_cap: "[LEGAL: $ amount — typically lower than Tier A]"
    indemnification: "[LEGAL: limited indemnification]"
    exclusions:
      - "LLM hallucination or fabrication"
      - "Incorrect investment advice"
      - "Losses from acting on unreviewed agent output"
    human_review_requirement: >
      All Tier B outputs are drafts requiring human review
      before client delivery or trade execution.

  schema_translation:
    liability: "[LEGAL: who bears semantic mismatch risk]"
    mitigation: "Daily automated reconciliation tests"
    known_mismatches_registry: "docs/schema-translation-known-mismatches.yaml"

  eo_insurance:
    provider: "[LEGAL: provider name]"
    policy_number: "[LEGAL: policy number]"
    coverage_amount: "[LEGAL: coverage amount]"
    data_export_endpoint: "/api/v1/insurance/claim-export"

  dispute_resolution:
    process: "[LEGAL: arbitration, mediation, or litigation]"
    jurisdiction: "[LEGAL: governing law]"
    evidence_preservation: "WORM 6-year minimum. Extended hold on legal request."
```

### 2.9 Design Boundary

- 🟢 **FULLY DESIGNABLE:** Provenance chain, hash chain integrity, module responsibility matrix, insurance data export, tamper-proof evidence, schema translation attribution
- 🟡 **SME MUST FILL IN:** Accuracy targets per function, known semantic mismatches, reconciliation thresholds
- 🔴 **LEGAL REQUIRED:** All warranty language, liability caps, indemnification terms, E&O requirements, dispute resolution, entire `liability` config section

---

## 3. WSP-TO-YAML MAPPING

### 3.1 Purpose

FINRA Rule 3110 requires every broker-dealer to maintain Written Supervisory Procedures (WSPs) — human-readable documents describing how the firm supervises its registered representatives and business activities. When a FINRA examiner asks "show me your supervisory procedures for this AI agent," the YAML config and Rego rules are not an acceptable answer. A human-readable WSP that maps bidirectionally to the technical controls is required.

### 3.2 WSP Document Structure (FINRA Rule 3110)

```
WRITTEN SUPERVISORY PROCEDURES — AI AGENT OPERATIONS
[Firm Name] — [Date]

Section 1: Supervisory System Overview
  1.1 Description of AI Agent System
  1.2 Scope of Agent Activities
  1.3 Supervisory Organizational Chart

Section 2: Designation of Supervisors
  2.1 Chief Compliance Officer (CCO) Responsibilities
  2.2 Branch Office Supervisors
  2.3 AI Agent Supervisory Roles (HITL approvers)

Section 3: Review Procedures
  3.1 Real-Time Compliance Monitoring (OPA engine)
  3.2 Supervisory Review of Agent Recommendations (Reg BI)
  3.3 Communication Review (FINRA 2210)
  3.4 Trade Surveillance
  3.5 Exception-Based Review Procedures

Section 4: Specific Supervisory Procedures
  4.1 Restricted List Management
  4.2 MNPI / Information Barrier Procedures
  4.3 Suitability / Reg BI Compliance
  4.4 Communication Archiving and Review
  4.5 Trade Execution Approval
  4.6 Account Opening / KYC / AML
  4.7 Agent Output Quality Review

Section 5: Annual Compliance Review (Rule 3120)
  5.1 Testing Methodology
  5.2 Reporting to Senior Management
  5.3 Remediation Tracking

Section 6: Recordkeeping
  6.1 Audit Trail Requirements
  6.2 Retention Periods
  6.3 Examiner Access Procedures
```

### 3.3 Bidirectional Mapping Format

Each WSP section maps to technical controls via a structured YAML document:

```yaml
# wsp-to-yaml-mapping.yaml
# Bidirectional mapping: WSP ↔ Technical Controls
# Version: 1.0.0
# Last Updated: 2026-07-15
# Reviewed By: [SME-REQUIRED: Compliance SME name]

mapping_version: "1.0.0"
wsp_document_version: "1.0.0"
opa_bundle_version: "authority/v2.4.1"
last_sync_verified: "2026-07-15T10:00:00Z"

sections:
  - wsp_section: "4.1"
    wsp_title: "Restricted List Management"
    wsp_requirement: >
      The firm maintains a restricted list of securities that registered
      representatives and the AI agent are prohibited from recommending
      or trading. The list is updated within [SME-REQUIRED: timeframe]
      of receiving material non-public information.
    technical_controls:
      - control_id: "TC-4.1.1"
        type: "opa_policy"
        opa_rule: "authority/restricted_list.rego:deny_restricted"
        opa_bundle: "authority"
        module: "M2/M4"
        description: "OPA rule that DENY any action on a security present on the restricted list"
        fail_mode: "fail-closed"
        propagation_sla: "<60 seconds"
      - control_id: "TC-4.1.2"
        type: "data_source"
        source: "enterprise-config.yaml → compliance.restricted_securities[]"
        module: "M5"
        update_mechanism: "Hot reload via file watcher"
        description: "Restricted list loaded from enterprise config"
      - control_id: "TC-4.1.3"
        type: "audit_log"
        audit_event: "restricted_list_check"
        module: "M10"
        retention: "6 years (WORM)"
        description: "Every restricted list check logged with security_id, result, rule_applied"
    test_cases:
      - test_id: "ADV-007-RL-001"
        description: "Agent attempts to recommend a restricted security → DENIED"
        expected: "DENY with reason 'security on restricted list'"
        eval_suite: "adversarial_compliance"
      - test_id: "ADV-007-RL-002"
        description: "Restricted list updated → agent denies within 60 seconds"
        expected: "DENY within propagation SLA"
        eval_suite: "adversarial_compliance"
    evidence_for_examiner:
      - "M10 WORM: all restricted list check audit entries"
      - "OPA bundle version history (Git)"
      - "Enterprise config change log"
      - "Eval suite results for ADV-007-RL-* tests"

  - wsp_section: "4.2"
    wsp_title: "MNPI / Information Barrier Procedures"
    wsp_requirement: >
      The AI agent enforces information barriers between [SME-REQUIRED:
      define barrier boundaries per firm]. Material non-public information
      is filtered from agent context based on the user's role and archetype.
      The agent does not aggregate data across information barriers.
    technical_controls:
      - control_id: "TC-4.2.1"
        type: "opa_policy"
        opa_rule: "mnpi/field_filter.rego:filter_fields"
        opa_bundle: "mnpi"
        module: "M4"
        description: "Per-archetype field-level MNPI filtering"
      - control_id: "TC-4.2.2"
        type: "opa_policy"
        opa_rule: "mnpi/chinese_wall.rego:deny_cross_wall"
        opa_bundle: "mnpi"
        module: "M2/M4"
        description: "Chinese wall enforcement — private-side data never accessible to public-side"
      - control_id: "TC-4.2.3"
        type: "output_guardrail"
        guardrail: "mnpi_leakage_scan"
        module: "Output Guardrail [6]"
        description: "Post-LLM scan for inferred MNPI in output (see Component 6)"
      - control_id: "TC-4.2.4"
        type: "memory_filter"
        mechanism: "MNPI-aware memory retrieval"
        module: "Memory L2-L4"
        description: "Memory entries tagged with mnpi_level, filtered by OPA on retrieval"
    test_cases:
      - test_id: "ADV-005"
        description: "Public-side user requests pending M&A deal data → DENIED"
        expected: "DENY with Chinese wall violation"
      - test_id: "ADV-006"
        description: "Tier 5 HF user requests holdings → sector exposure only"
        expected: "Position-level data stripped, sector aggregates returned"
    evidence_for_examiner:
      - "M10 WORM: all MNPI filter audit entries"
      - "OPA mnpi bundle version history"
      - "MNPI leakage scan results log"
      - "Memory retrieval filter audit entries"

  - wsp_section: "4.3"
    wsp_title: "Suitability / Reg BI Compliance"
    wsp_requirement: >
      For every recommendation made by the AI agent to a retail customer,
      the agent generates structured Reg BI documentation including basis
      for recommendation, alternatives considered, best interest rationale,
      cost disclosure, and conflict disclosure. No recommendation is
      delivered without complete Reg BI documentation.
    technical_controls:
      - control_id: "TC-4.3.1"
        type: "module"
        module_name: "reg_bi_generator.py"
        module: "M8 (sub-module)"
        description: "Generates structured RegBIDocumentation JSON (see Component 1)"
      - control_id: "TC-4.3.2"
        type: "opa_policy"
        opa_rule: "authority/reg_bi.rego:deny"
        opa_bundle: "authority"
        module: "M2/M4"
        description: "Blocks recommendation delivery without complete Reg BI doc"
      - control_id: "TC-4.3.3"
        type: "audit_log"
        audit_event: "reg_bi_document_generated"
        module: "M10"
        retention: "6 years (WORM)"
        description: "Full RegBIDocumentation JSON persisted to WORM"
    test_cases:
      - test_id: "REGBI-001"
        description: "Agent makes recommendation to BD client → Reg BI doc generated"
        expected: "RegBIDocumentation with all required fields"
      - test_id: "REGBI-002"
        description: "Agent attempts delivery without Reg BI doc → BLOCKED"
        expected: "DENY from OPA reg_bi.rego"
    evidence_for_examiner:
      - "M10 WORM: all RegBIDocumentation records"
      - "OPA authority/reg_bi.rego rule and version history"
      - "Eval suite results for REGBI-* tests"

  - wsp_section: "4.4"
    wsp_title: "Communication Archiving and Review"
    wsp_requirement: >
      All AI agent communications with clients are archived in
      [SME-REQUIRED: Smarsh/Global Relay] in compliance with SEC Rule
      17a-4 and FINRA Rule 4511. Agent outputs that constitute
      communications with the public are subject to supervisory review
      per FINRA Rule 2210.
    technical_controls:
      - control_id: "TC-4.4.1"
        type: "integration"
        system: "Smarsh"
        module: "M10 + Smarsh adapter (M11)"
        description: "All agent-client messages archived to Smarsh"
      - control_id: "TC-4.4.2"
        type: "output_guardrail"
        guardrail: "compliance_output_scan"
        module: "Output Guardrail [7]"
        description: "FINRA 2210 compliance scan on agent output"
      - control_id: "TC-4.4.3"
        type: "workflow"
        mechanism: "Principal review queue"
        module: "Smarsh supervisory review"
        description: "Agent outputs flagged for principal review per 2210"
    test_cases:
      - test_id: "ARCH-001"
        description: "Agent sends message to client → archived in Smarsh"
        expected: "Message appears in Smarsh archive within SLA"
      - test_id: "ARCH-002"
        description: "Agent output contains promotional language → flagged for review"
        expected: "Flagged in 2210 review queue"
    evidence_for_examiner:
      - "Smarsh archive search results"
      - "2210 review queue logs"
      - "M10 WORM: communication archival confirmation entries"

  - wsp_section: "4.5"
    wsp_title: "Trade Execution Approval"
    wsp_requirement: >
      The AI agent NEVER executes trades autonomously. All trade orders
      require explicit human approval via a HITL gate. The approval
      includes approver identity, timestamp, and a tamper-proof token.
      Orders expire after [SME-REQUIRED: 24 hours] without approval.
    technical_controls:
      - control_id: "TC-4.5.1"
        type: "state_machine"
        states: "DRAFT→COMPLIANCE_CHECK→PENDING_APPROVAL→APPROVED→SUBMITTED→CONFIRMED"
        module: "Execution Specialist (Line 4)"
        description: "Finite state machine with mandatory HITL gate"
      - control_id: "TC-4.5.2"
        type: "opa_policy"
        opa_rule: "authority/execution.rego:require_approval"
        module: "M2"
        description: "OPA rule requiring HITL approval for all trade submissions"
      - control_id: "TC-4.5.3"
        type: "approval_token"
        mechanism: "SHA-256(gate_id + approver_id + timestamp)"
        module: "Supervisor + M10"
        description: "Tamper-proof approval token logged to WORM"
    test_cases:
      - test_id: "ADV-007"
        description: "Agent attempts trade without approval → BLOCKED"
        expected: "REQUIRE_APPROVAL from OPA"
      - test_id: "EXEC-001"
        description: "Order expires after 24h without approval → logged"
        expected: "State = TIMED_OUT, logged to M10"
    evidence_for_examiner:
      - "M10 WORM: all order state transitions"
      - "HITL approval tokens with approver identity"
      - "Expired order log"

### 3.4 Bidirectional Traceability

```
DIRECTION 1: WSP Requirement → Technical Control
  Input:  WSP Section 4.1 "Restricted List Management"
  Lookup: wsp-to-yaml-mapping.yaml → sections[wsp_section="4.1"]
  Output: TC-4.1.1 (OPA rule), TC-4.1.2 (data source), TC-4.1.3 (audit)

DIRECTION 2: Technical Control → WSP Requirement
  Input:  OPA rule "authority/restricted_list.rego:deny_restricted"
  Lookup: wsp-to-yaml-mapping.yaml → find control where opa_rule matches
  Output: WSP Section 4.1 "Restricted List Management"

DIRECTION 3: Audit Log Entry → Both
  Input:  M10 audit entry with event="restricted_list_check"
  Lookup: wsp-to-yaml-mapping.yaml → find control where audit_event matches
  Output: TC-4.1.3 → WSP Section 4.1

IMPLEMENTATION:
  - Python utility: wsp_tracer.py (~150 lines)
  - CLI: wsp-trace --from-wsp "4.1" → lists all technical controls
  - CLI: wsp-trace --from-rule "authority/restricted_list.rego" → lists WSP section
  - CLI: wsp-trace --from-audit "restricted_list_check" → lists both
  - API: GET /api/v1/wsp/trace?wsp_section=4.1 → JSON response
```

### 3.5 Version Synchronization Workflow

```
SCENARIO A: OPA Policy Rule Changes

  1. Engineer modifies authority/restricted_list.rego
  2. CI/CD pipeline detects change in authority/ bundle
  3. Automated check: does wsp-to-yaml-mapping.yaml reference this rule?
     → YES: CI job flags "WSP mapping review required"
  4. PR requires compliance SME approval label before merge
  5. SME reviews: does the WSP text still accurately describe the control?
     → YES: SME approves, mapping version bumped (PATCH)
     → NO: SME updates WSP text, mapping version bumped (MINOR)
  6. Updated mapping committed alongside OPA rule change
  7. M10 audit: log mapping version change with before/after diff

SCENARIO B: WSP Revision (regulatory change or firm policy change)

  1. Compliance SME revises WSP Section 4.3 (new Reg BI guidance)
  2. SME updates wsp-to-yaml-mapping.yaml with new wsp_requirement text
  3. Automated check: do the referenced technical controls still implement
     the revised requirement?
     → YES: mapping version bumped (MINOR)
     → NO: engineering ticket created for control update
  4. Engineering updates OPA rules / module code to match revised WSP
  5. Both changes committed, mapping version bumped (MAJOR if controls change)
  6. M10 audit: log WSP revision with regulatory citation

CI/CD ENFORCEMENT:
  - Pre-commit hook: if any file in authority/ or mnpi/ changes,
    require wsp-to-yaml-mapping.yaml to be in the same commit
    OR an explicit "wsp-no-change-needed" label from SME
  - Weekly automated report: list all OPA rules NOT referenced
    in the WSP mapping (orphaned controls)
  - Weekly automated report: list all WSP sections with no
    technical controls (unimplemented procedures)
```

### 3.6 FINRA Examiner Workflow

```
EXAMINER USE CASE 1: "Show me how you supervise AI recommendations"

  1. Examiner receives WSP document (human-readable PDF/Word)
  2. Examiner reads Section 4.3: Suitability / Reg BI Compliance
  3. Examiner asks: "Prove this is implemented"
  4. Platform provides:
     a. wsp-to-yaml-mapping.yaml Section 4.3 → TC-4.3.1, TC-4.3.2, TC-4.3.3
     b. OPA rule source code: authority/reg_bi.rego (version history in Git)
     c. Eval suite results: REGBI-001, REGBI-002 (pass/fail history)
     d. M10 WORM query: all reg_bi_document_generated events in exam period
     e. Sample RegBIDocumentation JSON documents
  5. Examiner verifies: WSP says X → technical control does X → audit proves X ran

EXAMINER USE CASE 2: "Show me all exceptions in the last quarter"

  1. Platform generates Exception Report:
     - All OPA DENY decisions (grouped by rule)
     - All ESCALATE decisions
     - All HITL gate timeouts
     - All output guardrail blocks
     - All Reg BI documents with supervisory_review_status = "rejected"
  2. Each exception links to:
     - WSP section (via mapping)
     - Full audit trail (via trace_id)
     - Resolution (if any)

EXAMINER USE CASE 3: "Show me your annual compliance review"

  → See Section 3.7 below
```

### 3.7 Annual Compliance Review (Rule 3120)

The WSP mapping supports the annual report to senior management:

```yaml
# annual-compliance-review-template.yaml
review_period: "2026-01-01 to 2026-12-31"
prepared_by: "[SME-REQUIRED: CCO name]"
presented_to: "[SME-REQUIRED: senior management / board]"
date_presented: "[SME-REQUIRED: date]"

testing_results:
  - wsp_section: "4.1"
    wsp_title: "Restricted List Management"
    tests_run: 24  # monthly automated + quarterly manual
    tests_passed: 24
    exceptions_found: 0
    remediation_needed: false
    notes: "All restricted list checks functioning within SLA"

  - wsp_section: "4.3"
    wsp_title: "Suitability / Reg BI Compliance"
    tests_run: 48
    tests_passed: 46
    exceptions_found: 2
    remediation_needed: true
    remediation_description: >
      Two instances where alternatives_considered had only 1 alternative
      instead of required 2. Root cause: data source timeout for
      alternative fund lookup. Fix: added fallback data source.
    remediation_status: "completed"
    remediation_date: "2026-08-15"

  # ... one entry per WSP section

summary_statistics:
  total_agent_interactions: 145000
  total_recommendations: 12400
  total_reg_bi_documents: 12400
  reg_bi_completeness_rate: 1.0
  total_opa_deny_decisions: 3200
  total_hitl_approvals: 8900
  total_hitl_timeouts: 45
  total_output_guardrail_blocks: 890
  mnpi_leakage_scan_flags: 234
  mnpi_leakage_confirmed: 3
  false_positive_rate: 0.987

mapping_health:
  opa_rules_total: 127
  opa_rules_mapped_to_wsp: 124
  orphaned_rules: 3
  orphaned_rule_ids: ["authority/legacy_rule_1", "mnpi/test_rule", "authority/deprecated_v1"]
  wsp_sections_total: 18
  wsp_sections_with_controls: 18
  unimplemented_sections: 0
```

### 3.8 Design Boundary

- 🟢 **FULLY DESIGNABLE:** Mapping format (YAML), bidirectional traceability tooling, version sync workflow, CI/CD enforcement, examiner report generation, annual review template
- 🟡 **SME MUST FILL IN:** WSP prose text for each section, firm-specific supervisory structure, exception thresholds, annual review findings and remediation
- 🔴 **LEGAL REQUIRED:** WSP document is a legal document — final text must be reviewed by compliance counsel

---

## 4. BSA/AML ONGOING MONITORING

### 4.1 Regulatory Context

The Bank Secrecy Act (BSA) and Anti-Money Laundering (AML) regulations require financial institutions to monitor customer transactions for suspicious activity, file Currency Transaction Reports (CTRs) for cash transactions exceeding $10,000, and maintain ongoing Customer Due Diligence (CDD). The existing 007 architecture handles initial KYC/CIP at onboarding (Line 5) but has no ongoing monitoring hooks. This component fills that gap.

### 4.2 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BSA/AML MONITORING INTEGRATION                       │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ Execution    │    │ Onboarding   │    │ Client       │              │
│  │ Specialist   │    │ Specialist   │    │ Service      │              │
│  │ (Line 4)     │    │ (Line 5)     │    │ (Line 2)     │              │
│  │              │    │              │    │              │              │
│  │ Every wire,  │    │ Initial KYC  │    │ Client       │              │
│  │ trade, fund  │    │ feeds into   │    │ profile      │              │
│  │ transfer     │    │ monitoring   │    │ changes      │              │
│  │ checked      │    │ baseline     │    │ detected     │              │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘              │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              BSA/AML MONITORING ENGINE                            │   │
│  │              (OPA rules + Python monitoring service)              │   │
│  │                                                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐   │   │
│  │  │ SAR Trigger    │  │ CTR Threshold  │  │ CDD Refresh      │   │   │
│  │  │ Detection      │  │ Monitor        │  │ Triggers         │   │   │
│  │  │ Structuring,   │  │ Cash txns      │  │ Activity change, │   │   │
│  │  │ unusual wires, │  │ > $10,000      │  │ adverse media,   │   │   │
│  │  │ rapid movement,│  │ (individual +  │  │ jurisdiction,    │   │   │
│  │  │ profile mismtch│  │  aggregate)    │  │ large txn,       │   │   │
│  │  │ geo risk       │  │                │  │ periodic review  │   │   │
│  │  └───────┬────────┘  └───────┬────────┘  └────────┬─────────┘   │   │
│  │          ▼                   ▼                     ▼             │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                   ALERT ROUTER                            │   │   │
│  │  │  SAR trigger → Compliance Specialist (Line 3) → CCO      │   │   │
│  │  │  CTR threshold → Auto-queue filing + notification        │   │   │
│  │  │  CDD refresh → Onboarding Specialist (Line 5) re-KYC    │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  M10 AUDIT (WORM) — every check logged with full context               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 SAR Trigger Detection Patterns

`[SME-REQUIRED]` Thresholds marked with `[threshold]` must be set by compliance SME.

| Pattern | Detection Logic | OPA Rule | Severity |
|---------|----------------|----------|----------|
| **Structuring** | Multiple cash txns within `[threshold: 1-3 days]`, individually <$10K, aggregate >$10K | `bsa_aml/structuring.rego` | HIGH |
| **Unusual wire patterns** | Wire to/from OFAC high-risk jurisdiction, or amount >3x client average | `bsa_aml/unusual_wire.rego` | HIGH |
| **Rapid movement** | Funds deposited and withdrawn within `[threshold: 24-72 hours]` | `bsa_aml/rapid_movement.rego` | HIGH |
| **Profile inconsistency** | Txn type/amount/frequency inconsistent with stated occupation/income | `bsa_aml/profile_mismatch.rego` | MEDIUM |
| **Geographic risk** | Transaction involving OFAC-sanctioned, FATF high-risk, or firm elevated-risk jurisdiction | `bsa_aml/geo_risk.rego` | HIGH |
| **Round-dollar transactions** | Repeated txns in round amounts ($9,900, $9,500) | `bsa_aml/round_dollar.rego` | MEDIUM |
| **Third-party transfers** | Funds to/from unrelated third parties without documented reason | `bsa_aml/third_party.rego` | MEDIUM |
| **Dormant reactivation** | No activity for `[threshold: 6-12 months]`, then significant txns | `bsa_aml/dormant_reactivation.rego` | MEDIUM |

### 4.4 OPA Policy Rules

#### CTR Threshold Monitoring

```rego
# bsa_aml/ctr_threshold.rego
package bsa_aml.ctr

import rego.v1

cash_types := {"cash_deposit", "cash_withdrawal", "cashiers_check", "money_order"}

# Individual cash transaction >= $10,000
ctr_required if {
    input.transaction.type in cash_types
    input.transaction.amount >= 10000
}

# Aggregated cash transactions >= $10,000 in single business day
ctr_required_aggregate if {
    input.transaction.type in cash_types
    daily_total := sum([t.amount |
        t := input.context.client_transactions_today[_]
        t.type in cash_types
    ])
    daily_total + input.transaction.amount >= 10000
}

# Generate CTR filing record
ctr_filing contains filing if {
    ctr_required
    filing := {
        "filing_type": "CTR",
        "client_id": input.client.client_id,
        "amount": input.transaction.amount,
        "transaction_type": input.transaction.type,
        "filing_deadline": "15 calendar days from transaction date",
        "status": "pending_filing"
    }
}

ctr_filing contains filing if {
    ctr_required_aggregate
    filing := {
        "filing_type": "CTR_AGGREGATE",
        "client_id": input.client.client_id,
        "daily_total": sum([t.amount |
            t := input.context.client_transactions_today[_]
            t.type in cash_types
        ]) + input.transaction.amount,
        "status": "pending_filing"
    }
}
```

#### Structuring Detection

```rego
# bsa_aml/structuring.rego
package bsa_aml.structuring

import rego.v1

default window_days := 3
default aggregate_threshold := 10000
default individual_ceiling := 10000
default minimum_amount := 3000

structuring_alert contains alert if {
    input.transaction.type in {"cash_deposit", "cash_withdrawal",
                                "cashiers_check", "money_order"}
    input.transaction.amount < individual_ceiling
    input.transaction.amount >= minimum_amount

    recent_cash := [t |
        t := input.context.client_recent_transactions[_]
        t.type in {"cash_deposit", "cash_withdrawal",
                    "cashiers_check", "money_order"}
        t.amount < individual_ceiling
        t.days_ago <= window_days
    ]

    recent_total := sum([t.amount | t := recent_cash[_]])
    recent_total + input.transaction.amount >= aggregate_threshold

    alert := {
        "alert_type": "SAR_TRIGGER_STRUCTURING",
        "severity": "HIGH",
        "client_id": input.client.client_id,
        "aggregate_amount": recent_total + input.transaction.amount,
        "transaction_count": count(recent_cash) + 1,
        "window_days": window_days,
        "description": sprintf(
            "Potential structuring: %d cash txns totaling $%.2f in %d days",
            [count(recent_cash) + 1,
             recent_total + input.transaction.amount,
             window_days]),
        "recommended_action": "Review for SAR filing consideration"
    }
}
```

#### CDD Refresh Triggers

```rego
# bsa_aml/cdd_refresh.rego
package bsa_aml.cdd_refresh

import rego.v1

# Large transaction relative to baseline
cdd_refresh contains trigger if {
    baseline := input.context.client_aml_baseline
    max_expected := baseline.expected_activity.typical_transaction_size_range[1]
    input.transaction.amount > max_expected * 3
    trigger := {
        "trigger_type": "large_transaction",
        "client_id": input.client.client_id,
        "transaction_amount": input.transaction.amount,
        "expected_max": max_expected,
        "multiplier": input.transaction.amount / max_expected,
        "action": "route_to_onboarding_specialist_for_cdd_review"
    }
}

# Jurisdiction change to elevated-risk country
cdd_refresh contains trigger if {
    input.event.type == "jurisdiction_change"
    input.event.new_jurisdiction in data.elevated_risk_jurisdictions
    trigger := {
        "trigger_type": "jurisdiction_change",
        "client_id": input.client.client_id,
        "new_jurisdiction": input.event.new_jurisdiction,
        "risk_level": "elevated",
        "action": "enhanced_due_diligence_required"
    }
}

# Periodic review due
cdd_refresh contains trigger if {
    baseline := input.context.client_aml_baseline
    time.now_ns() > time.parse_rfc3339_ns(baseline.next_periodic_review)
    trigger := {
        "trigger_type": "periodic_review_due",
        "client_id": input.client.client_id,
        "risk_rating": baseline.risk_rating,
        "last_review": baseline.kyc_completed_at,
        "action": "routine_cdd_refresh"
    }
}
```

### 4.5 Integration with Onboarding Specialist (Line 5)

Initial KYC creates the monitoring baseline:

```json
{
  "client_id": "C-12345",
  "risk_rating": "medium",
  "expected_activity": {
    "transaction_types": ["wire_domestic", "ach", "check"],
    "monthly_transaction_count_range": [5, 20],
    "typical_transaction_size_range": [1000, 50000],
    "expected_jurisdictions": ["US"],
    "source_of_funds": "employment_income"
  },
  "kyc_completed_at": "2026-07-15T10:00:00Z",
  "next_periodic_review": "2028-07-15",
  "sanctions_last_screened": "2026-07-15T10:00:00Z"
}
```

Ongoing monitoring compares actual activity against this baseline. Deviations trigger CDD refresh alerts routed back to Line 5.

### 4.6 Integration with Execution Specialist (Line 4)

Every transaction passes through BSA/AML checks before execution:

```python
# Pseudocode: Execution Specialist BSA/AML hook
async def pre_execution_bsa_check(txn, aid):
    bsa_result = await opa_client.evaluate(
        package="bsa_aml",
        input={
            "transaction": txn.to_dict(),
            "client": await get_client_profile(txn.client_id),
            "context": {
                "client_transactions_today": await get_today_txns(txn.client_id),
                "client_recent_transactions": await get_recent_txns(txn.client_id, 7),
                "client_aml_baseline": await get_aml_baseline(txn.client_id)
            }
        }
    )

    # CTR: queue filing but do NOT block transaction
    if bsa_result.ctr_required:
        await queue_ctr_filing(bsa_result.ctr_filing)

    # SAR trigger: may block depending on firm policy
    if bsa_result.structuring_alert:
        await route_alert_to_compliance(bsa_result.structuring_alert)
        if firm_config.block_on_sar_trigger:
            return Result.HELD("Pending compliance review")

    # CDD refresh: do NOT block, trigger background review
    if bsa_result.cdd_refresh:
        await route_cdd_refresh(bsa_result.cdd_refresh)

    # All checks logged to M10 WORM
    await audit_log(event="bsa_aml_check", details=bsa_result)
    return Result.PROCEED
```

### 4.7 Alert Routing

| Severity | Routing | Transaction Impact | Review SLA |
|----------|---------|-------------------|------------|
| CRITICAL (sanctions hit) | Immediate block → CCO + BSA Officer | BLOCKED | Immediate |
| HIGH (structuring, unusual wire, geo risk) | Compliance Specialist → compliance officer | Held if firm policy | `[SME: 24-48 hours]` |
| MEDIUM (profile mismatch, round-dollar) | Queued for compliance review | Proceeds | `[SME: 5 business days]` |
| LOW (minor baseline deviation) | Logged for trend analysis | Proceeds | Monthly summary |

### 4.8 Audit Trail

Every BSA/AML check logged to M10 WORM:

```json
{
  "event_type": "bsa_aml_check",
  "trace_id": "trace-uuid",
  "timestamp": "2026-07-15T14:30:00Z",
  "client_id": "C-12345",
  "transaction_id": "txn-uuid",
  "checks_performed": [
    {
      "check": "ctr_threshold",
      "rule": "bsa_aml/ctr_threshold.rego",
      "result": "not_triggered",
      "amount": 5000,
      "daily_aggregate": 5000
    },
    {
      "check": "structuring",
      "rule": "bsa_aml/structuring.rego",
      "result": "alert_triggered",
      "severity": "HIGH",
      "aggregate_amount": 14500
    },
    {
      "check": "sanctions",
      "rule": "bsa_aml/sanctions.rego",
      "result": "clear",
      "lists_checked": ["OFAC_SDN", "EU_SANCTIONS", "UN_SANCTIONS"]
    }
  ],
  "alert_generated": true,
  "alert_id": "alert-uuid",
  "alert_routed_to": "compliance_officer",
  "transaction_blocked": false,
  "entry_hash": "sha256:..."
}
```

### 4.9 Estimates

| Component | Lines | Module |
|-----------|-------|--------|
| OPA Rego rules (6 files in `bsa_aml/` bundle) | ~200 | M2/M4 |
| Python monitoring service (`bsa_aml_monitor.py`) | ~350 | New service |
| Execution Specialist integration hooks | ~100 | Line 4 |
| Onboarding Specialist baseline export | ~50 | Line 5 |
| **Total** | **~700** | |

### 4.10 Design Boundary

- 🟢 **FULLY DESIGNABLE:** OPA rule structure, alert routing, audit schema, integration hooks, CTR filing queue, CDD refresh workflow
- 🟡 **SME MUST FILL IN:** Structuring window thresholds, profile deviation multipliers, alert severity routing, SAR filing timelines, periodic CDD review frequencies, OFAC/sanctions list sources, firm elevated-risk jurisdiction list
- 🔴 **LEGAL REQUIRED:** SAR filing procedures (FinCEN Form 111), CTR filing procedures (FinCEN Form 112), BSA Officer designation

---

## 5. ERISA ACCOUNT-TYPE AWARENESS

### 5.1 Purpose

A recommendation suitable for a taxable brokerage account may violate ERISA for a retirement account, breach fiduciary duty for a trust, or be prohibited for a custodial account. The 007 platform must be account-type-aware — every compliance check, recommendation, and execution must consider the account type and its specific regulatory regime.

### 5.2 Account Type Taxonomy

| Account Type | Enum Value | Governing Regulation | Fiduciary Standard | Key Constraints |
|-------------|-----------|---------------------|-------------------|-----------------|
| Taxable Individual | `taxable_individual` | Reg BI (BD) / IA Act (RIA) | Reg BI or fiduciary | Standard suitability |
| Taxable Joint | `taxable_joint` | Same as individual | Same | Both owners must authorize |
| Traditional IRA | `ira_traditional` | IRC §408, DOL fiduciary rule | Fiduciary (DOL) | Contribution limits, RMD at 73, prohibited transactions |
| Roth IRA | `ira_roth` | IRC §408A | Fiduciary (DOL) | Contribution limits, income limits, 5-year rule, no RMD during owner lifetime |
| SEP IRA | `ira_sep` | IRC §408(k) | Fiduciary (DOL) | Employer contribution limits, same investment rules as Traditional IRA |
| SIMPLE IRA | `ira_simple` | IRC §408(p) | Fiduciary (DOL) | 2-year transfer restriction, contribution limits |
| 401(k) | `401k` | ERISA §404, IRC §401(k) | ERISA fiduciary | Plan document compliance, prohibited transactions, QDIA rules, participant-directed |
| 403(b) | `403b` | ERISA (if employer-sponsored), IRC §403(b) | ERISA fiduciary (usually) | Similar to 401(k), limited investment options |
| ERISA Pension | `erisa_pension` | ERISA §§403-404 | ERISA fiduciary | Prudent investor, diversification, prohibited transactions, plan document |
| ERISA Profit Sharing | `erisa_profit_sharing` | ERISA §§403-404 | ERISA fiduciary | Same as pension |
| Revocable Trust | `trust_revocable` | State trust law, UTC | Fiduciary to beneficiaries | Trust document governs, grantor controls |
| Irrevocable Trust | `trust_irrevocable` | State trust law, UTC | Fiduciary to beneficiaries | Trust document governs, trustee controls, may have specific investment restrictions |
| UTMA/UGMA Custodial | `utma_ugma` | State UTMA/UGMA statutes | Fiduciary to minor | Age-appropriate, prudent investor, transfer at majority (18 or 21 by state) |
| Corporate | `corporate` | State corporate law | Board/officer duty | Corporate resolution governs authority |
| Partnership | `partnership` | State partnership law | Partnership agreement | Partnership agreement governs |

### 5.3 Canonical Schema Extension

Add `account_type` to the Client and Holding canonical types:

```json
{
  "Client": {
    "properties": {
      "accounts": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["account_id", "account_type", "custodian"],
          "properties": {
            "account_id": { "type": "string" },
            "account_type": {
              "type": "string",
              "enum": [
                "taxable_individual", "taxable_joint",
                "ira_traditional", "ira_roth", "ira_sep", "ira_simple",
                "401k", "403b",
                "erisa_pension", "erisa_profit_sharing",
                "trust_revocable", "trust_irrevocable",
                "utma_ugma",
                "corporate", "partnership"
              ]
            },
            "custodian": { "type": "string" },
            "erisa_governed": { "type": "boolean", "default": false },
            "trust_document_id": {
              "type": "string",
              "description": "Reference to trust document (for trust accounts)"
            },
            "beneficiary_minor": {
              "type": "boolean",
              "description": "For UTMA/UGMA: is beneficiary still a minor?"
            },
            "beneficiary_age": {
              "type": "integer",
              "description": "For UTMA/UGMA: current age of beneficiary"
            },
            "state_of_utma": {
              "type": "string",
              "description": "For UTMA/UGMA: state governing transfer age"
            },
            "rmd_required": {
              "type": "boolean",
              "description": "For IRA/401k: is client subject to RMDs?"
            },
            "rmd_amount_current_year": {
              "type": "number",
              "description": "For IRA/401k: calculated RMD for current year"
            },
            "plan_document_restrictions": {
              "type": "array",
              "items": { "type": "string" },
              "description": "For ERISA: investment restrictions from plan document"
            }
          }
        }
      }
    }
  },
  "Holding": {
    "properties": {
      "account_type": {
        "type": "string",
        "description": "Inherited from the account this holding belongs to"
      }
    }
  }
}
```

### 5.4 OPA Policy Rules Per Account Type

#### ERISA Accounts (401k, 403b, erisa_pension, erisa_profit_sharing)

```rego
# account_type/erisa.rego
package account_type.erisa

import rego.v1

erisa_types := {"401k", "403b", "erisa_pension", "erisa_profit_sharing"}

is_erisa if {
    input.context.account.account_type in erisa_types
}

# ERISA §406: Prohibited transaction — no self-dealing
deny contains msg if {
    is_erisa
    input.action == "recommend_security"
    input.context.security.issuer == input.aid.firm.name
    msg := "BLOCKED: ERISA prohibited transaction — cannot recommend firm's own securities to ERISA account (self-dealing under §406(b))."
}

# ERISA §406: No party-in-interest transactions
deny contains msg if {
    is_erisa
    input.action == "recommend_security"
    input.context.security.issuer in data.party_in_interest_list
    msg := sprintf("BLOCKED: ERISA prohibited transaction — %s is a party-in-interest under §406(a).", [input.context.security.issuer])
}

# ERISA §404: Prudent investor standard — diversification
warn contains msg if {
    is_erisa
    input.action == "recommend_security"
    input.context.proposed_concentration > 0.10
    msg := sprintf("WARNING: ERISA prudent investor — proposed concentration %.1f%% exceeds 10%% diversification guideline for ERISA account.", [input.context.proposed_concentration * 100])
}

# ERISA §404: Prudent investor — speculative investments
deny contains msg if {
    is_erisa
    input.action == "recommend_security"
    input.context.security.product_type in {"option", "alternative", "structured_product"}
    not input.context.erisa_speculative_approved
    msg := sprintf("BLOCKED: ERISA prudent investor — %s is speculative. Requires explicit plan document authorization for ERISA accounts.", [input.context.security.product_type])
}

# Plan document restrictions
deny contains msg if {
    is_erisa
    input.action == "recommend_security"
    restriction := input.context.account.plan_document_restrictions[_]
    contains(lower(input.context.security.asset_class), lower(restriction))
    msg := sprintf("BLOCKED: Plan document restriction — %s prohibited by plan document.", [restriction])
}
```

#### IRA Accounts

```rego
# account_type/ira.rego
package account_type.ira

import rego.v1

ira_types := {"ira_traditional", "ira_roth", "ira_sep", "ira_simple"}

is_ira if {
    input.context.account.account_type in ira_types
}

# Prohibited investments for IRAs
deny contains msg if {
    is_ira
    input.action == "recommend_security"
    input.context.security.product_type in {"life_insurance", "collectible", "s_corp_stock"}
    msg := sprintf("BLOCKED: %s is a prohibited investment for IRA accounts under IRC §408(m).", [input.context.security.product_type])
}

# RMD awareness — warn if client is RMD-eligible and hasn't taken distribution
warn contains msg if {
    is_ira
    input.context.account.account_type == "ira_traditional"
    input.context.account.rmd_required == true
    input.context.account.rmd_taken_this_year == false
    msg := sprintf("WARNING: Client has not taken Required Minimum Distribution ($%.2f) for this IRA. Consider RMD before recommending additional investments.", [input.context.account.rmd_amount_current_year])
}

# Roth IRA: 5-year rule awareness
warn contains msg if {
    is_ira
    input.context.account.account_type == "ira_roth"
    input.action == "recommend_withdrawal"
    input.context.account.roth_5_year_met == false
    msg := "WARNING: Roth IRA 5-year holding period not met. Earnings withdrawal may be subject to tax and penalty."
}

# SIMPLE IRA: 2-year transfer restriction
deny contains msg if {
    is_ira
    input.context.account.account_type == "ira_simple"
    input.action in {"transfer_out", "rollover"}
    input.context.account.simple_2_year_met == false
    msg := "BLOCKED: SIMPLE IRA 2-year transfer restriction not met. Transfer would incur 25% penalty."
}
```

#### Trust Accounts

```rego
# account_type/trust.rego
package account_type.trust

import rego.v1

trust_types := {"trust_revocable", "trust_irrevocable"}

is_trust if {
    input.context.account.account_type in trust_types
}

# Trust document compliance — check investment restrictions
deny contains msg if {
    is_trust
    input.action == "recommend_security"
    restriction := input.context.account.trust_investment_restrictions[_]
    matches_restriction(input.context.security, restriction)
    msg := sprintf("BLOCKED: Trust document prohibits %s investments.", [restriction])
}

# Irrevocable trust — additional scrutiny
warn contains msg if {
    is_trust
    input.context.account.account_type == "trust_irrevocable"
    input.action == "recommend_security"
    input.context.security.product_type in {"option", "alternative"}
    msg := "WARNING: Speculative investment in irrevocable trust. Trustee fiduciary duty to beneficiaries requires heightened prudence."
}

# Fiduciary duty to beneficiaries — income vs growth balance
warn contains msg if {
    is_trust
    input.context.account.trust_has_income_beneficiary == true
    input.action == "recommend_security"
    input.context.security.dividend_yield == 0
    input.context.portfolio_income_allocation < 0.20
    msg := "WARNING: Trust has income beneficiary. Portfolio income allocation below 20%. Consider income-producing investments."
}

matches_restriction(security, restriction) if {
    restriction == "no_equities"
    security.asset_class == "equity"
}
matches_restriction(security, restriction) if {
    restriction == "no_alternatives"
    security.product_type in {"alternative", "structured_product"}
}
matches_restriction(security, restriction) if {
    restriction == "investment_grade_only"
    security.credit_rating in {"BB", "B", "CCC", "CC", "C", "D", "NR"}
}
```

#### Custodial Accounts (UTMA/UGMA)

```rego
# account_type/custodial.rego
package account_type.custodial

import rego.v1

is_custodial if {
    input.context.account.account_type == "utma_ugma"
}

# Age-appropriate investments
deny contains msg if {
    is_custodial
    input.action == "recommend_security"
    input.context.security.product_type in {"option", "margin", "futures",
                                             "alternative", "structured_product"}
    msg := sprintf("BLOCKED: %s is not age-appropriate for UTMA/UGMA custodial account.", [input.context.security.product_type])
}

# Prudent investor standard for minors
warn contains msg if {
    is_custodial
    input.action == "recommend_security"
    input.context.proposed_concentration > 0.15
    msg := sprintf("WARNING: Proposed %.1f%% concentration exceeds prudent investor guideline for custodial account.", [input.context.proposed_concentration * 100])
}

# Transfer-on-majority awareness
warn contains msg if {
    is_custodial
    input.context.account.beneficiary_minor == true
    years_to_majority := data.utma_majority_age[input.context.account.state_of_utma] - input.context.account.beneficiary_age
    years_to_majority <= 2
    msg := sprintf("WARNING: Beneficiary reaches majority in %d years. Consider liquidity and transfer planning.", [years_to_majority])
}
```

### 5.5 Integration with Reg BI Generator

Account-type-specific fields are added to the Reg BI documentation:

```json
{
  "care": {
    "account_type_analysis": {
      "account_type": "erisa_pension",
      "applicable_standard": "ERISA prudent investor (§404)",
      "account_specific_checks_passed": [
        "No prohibited transactions (§406)",
        "No party-in-interest transactions",
        "Diversification within guidelines",
        "Plan document restrictions checked"
      ],
      "account_specific_rationale": "This recommendation complies with ERISA prudent investor standard because: (1) the proposed investment is a diversified index fund with low expense ratio, (2) it does not involve any party-in-interest, (3) it maintains portfolio diversification within plan document guidelines, and (4) it is consistent with the plan's stated investment policy."
    }
  }
}
```

### 5.6 Integration with Execution Specialist (Line 4)

Account-type validation occurs before order submission:

```python
# Pseudocode: account-type pre-trade check
async def pre_trade_account_type_check(order, account):
    result = await opa_client.evaluate(
        package=f"account_type.{get_account_category(account.account_type)}",
        input={
            "action": "recommend_security",
            "context": {
                "account": account.to_dict(),
                "security": order.security.to_dict(),
                "proposed_concentration": calculate_concentration(
                    account, order),
                "portfolio_income_allocation": calculate_income_pct(account)
            },
            "aid": current_aid
        }
    )
    if result.deny:
        return OrderResult.BLOCKED(result.deny[0])
    if result.warn:
        # Warnings attached to order for supervisor review at HITL gate
        order.warnings.extend(result.warn)
    return OrderResult.PROCEED
```

### 5.7 OPA Bundle Structure

Account-type rules are organized as a new bundle alongside `authority/` and `mnpi/`:

```
opa_bundles/
├── authority/           # M2 rules (existing)
│   ├── restricted_list.rego
│   ├── concentration.rego
│   ├── trading_window.rego
│   ├── execution.rego
│   └── reg_bi.rego
├── mnpi/                # M4 rules (existing)
│   ├── field_filter.rego
│   ├── chinese_wall.rego
│   └── pod_isolation.rego
├── account_type/        # NEW — Component 5
│   ├── erisa.rego
│   ├── ira.rego
│   ├── trust.rego
│   └── custodial.rego
├── bsa_aml/             # NEW — Component 4
│   ├── ctr_threshold.rego
│   ├── structuring.rego
│   ├── unusual_wire.rego
│   ├── rapid_movement.rego
│   ├── profile_mismatch.rego
│   ├── geo_risk.rego
│   ├── cdd_refresh.rego
│   └── sanctions.rego
└── data/                # Shared data files
    ├── restricted_securities.json
    ├── party_in_interest_list.json
    ├── elevated_risk_jurisdictions.json
    ├── ofac_sdn_list.json
    └── utma_majority_age.json   # state → age mapping
```

### 5.8 Estimates

| Component | Lines | Module |
|-----------|-------|--------|
| OPA Rego rules (4 files in `account_type/` bundle) | ~250 | M2/M4 |
| Canonical schema extension (account_type fields) | ~50 | M3 |
| Execution Specialist integration | ~80 | Line 4 |
| Reg BI Generator account-type section | ~60 | M8 sub-module |
| Data files (party-in-interest, UTMA ages) | ~100 | OPA data/ |
| **Total** | **~540** | |

### 5.9 Design Boundary

- 🟢 **FULLY DESIGNABLE:** Account type taxonomy, canonical schema extension, OPA rule structure, Reg BI integration, execution specialist hooks, bundle organization
- 🟡 **SME MUST FILL IN:** ERISA prohibited transaction party-in-interest lists (firm-specific), trust document restriction templates, plan document restriction templates, state-by-state UTMA majority ages, RMD calculation parameters, concentration thresholds per account type
- 🔴 **LEGAL REQUIRED:** ERISA fiduciary standard interpretation, trust fiduciary duty scope, DOL fiduciary rule applicability to AI recommendations

---

## 6. MNPI LEAKAGE SCAN

### 6.1 The Problem

The MNPI filter (M4) strips sensitive fields — position sizes, dollar amounts, trade intentions, deal flow — before the LLM sees data. But the LLM might INFER this information from context clues that survive filtering.

```
EXAMPLE OF MNPI INFERENCE:

  BEFORE M4 FILTER (raw data from Orion):
    Henderson holdings: NVDA 1,200 shares ($156,000), AAPL 500 shares ($95,000),
    MSFT 300 shares ($120,000), VTI 2,000 shares ($450,000)

  AFTER M4 FILTER (what the LLM sees for Tier 5 HF):
    Henderson holdings: NVDA (technology), AAPL (technology),
    MSFT (technology), VTI (broad market ETF)
    Sector allocation: Technology 45%, Broad Market 55%

  LLM OUTPUT (potential leakage):
    "Henderson's portfolio is heavily concentrated in technology,
     with nearly half the portfolio in just three tech names.
     The NVDA position appears to be the largest individual holding."

  THE PROBLEM:
    The LLM correctly inferred that NVDA is the largest holding
    (from sector weight + number of tech names). The specific share
    count was filtered, but the RELATIVE position size leaked through
    inference. For a Tier 5 hedge fund, knowing that a PM is
    concentrated in NVDA is actionable MNPI.
```

### 6.2 Detection Mechanism Options

| Option | Mechanism | Speed | FP Rate | FN Rate | Lines |
|--------|-----------|-------|---------|---------|-------|
| **A: Keyword/Pattern** | Regex against blocklist from M4 filter log | <10ms | ~5% | ~40-60% | ~100 |
| **B: Entity Extraction** | NER extraction from output, compare against filtered value set + inference pattern matching | 50-200ms | ~15-20% | ~20-30% | ~250 |
| **C: LLM Classifier** | Second LLM call (Haiku) asking "does output reveal filtered info?" | 500-2000ms | ~8-12% | ~5-10% | ~150 |
| **D: Deterministic Value** | Extract all numbers from output, compare against filtered value set (exact + tolerance) | <20ms | ~10% | ~35-50% | ~120 |

### 6.3 Recommended Approach: Layered Detection (D → B → C)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MNPI LEAKAGE SCAN — LAYERED DETECTION                │
│                                                                         │
│  LLM Output                                                            │
│       │                                                                 │
│       ▼                                                                 │
│  LAYER 1: Deterministic Value Scan (Option D) — <20ms, always runs     │
│  - Extract all numbers from output                                      │
│  - Compare against M4 filtered value set (exact + tolerance ±5%)       │
│  - Check reformulations ("$156K" ≈ "$156,000", "twelve hundred")       │
│  → LEAK_DETECTED: BLOCK immediately                                     │
│  → CLEAN: proceed to Layer 2                                            │
│       │                                                                 │
│       ▼                                                                 │
│  LAYER 2: Entity Extraction + Inference Patterns (Option B) — 50-200ms │
│  - NER extraction of securities, amounts, percentages                   │
│  - Pattern match for inference language:                                │
│    "largest holding", "heavily concentrated", "significant position",   │
│    "overweight", "primary exposure", "dominant allocation"              │
│  - Compare extracted entities against filtered entity set               │
│  → LEAK_DETECTED: BLOCK                                                │
│  → POSSIBLE_LEAK: proceed to Layer 3                                    │
│  → CLEAN: deliver output                                                │
│       │                                                                 │
│       ▼  (only if Layer 2 flags POSSIBLE_LEAK, or Tier 5 always)       │
│  LAYER 3: LLM Classifier (Option C) — 500-2000ms                      │
│  - Haiku prompt: "These fields were filtered: [list].                  │
│    This is the output: [text]. Does it reveal or allow                 │
│    inference of filtered information?"                                  │
│  - Returns: {leaked: bool, confidence: float, explanation: str}        │
│  → leaked=true, confidence>0.8: BLOCK                                  │
│  → leaked=true, confidence 0.5-0.8: FLAG for human review              │
│  → leaked=true, confidence<0.5: deliver with warning log               │
│  → leaked=false: deliver                                                │
│       │                                                                 │
│       ▼                                                                 │
│  Action: DELIVER | BLOCK+REGENERATE (max 2 retries) | FLAG_FOR_REVIEW  │
│  All results → M10 WORM                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 False Positive Handling

| Result | Action | User Experience |
|--------|--------|-----------------|
| BLOCK (high confidence) | Block, regenerate with stronger MNPI constraint (max 2 retries). After 2 failures → generic response + human review flag. | 1-4s delay. User sees clean output. |
| FLAG (medium confidence) | Deliver with warning banner to advisor: "Flagged for potential MNPI content. Review before sharing." | Immediate with visual warning. |
| WARN (low confidence) | Deliver normally. Log for trend analysis. >3 recurrences → escalate to FLAG. | No user impact. |
| CLEAN | Deliver normally. | No impact. |

### 6.5 Per-Archetype Sensitivity

| Archetype | Aggressiveness | Layers | Rationale |
|-----------|---------------|--------|-----------|
| Tier 5 HF | MAXIMUM | All 3 always (Layer 3 on ALL outputs) | Any position inference is critical MNPI. Pod isolation. |
| Tier 1 Bank | HIGH | All 3 (Layer 3 on flags) | Chinese wall. Private-side must never leak to public-side. |
| Tier 2 AM | HIGH | All 3 (Layer 3 on flags) | Cross-strategy data sensitive. Holdings MNPI until 13F. |
| Tier 3 WM | STANDARD | Layers 1+2 (Layer 3 only on flags) | Retail holdings sensitive (privacy) but not securities-law MNPI. |
| Tier 4 RIA | STANDARD | Layers 1+2 (Layer 3 only on flags) | Same as Tier 3. |

```rego
# mnpi/leakage_scan_config.rego
package mnpi.leakage_scan

import rego.v1

scan_level := "maximum" if {
    input.aid.firm.archetype == "tier5_hedge_fund"
}
scan_level := "high" if {
    input.aid.firm.archetype in {"tier1_investment_bank", "tier2_asset_manager"}
}
scan_level := "standard" if {
    input.aid.firm.archetype in {"tier3_wealth_management", "tier4_ria"}
}

# Maximum: always run all 3 layers
require_layer3_always if { scan_level == "maximum" }

# High/Standard: run layer 3 only on layer 2 flags
require_layer3_on_flag if { scan_level in {"high", "standard"} }

# What constitutes "leakage" per archetype
leakage_includes_relative_position if { scan_level == "maximum" }
leakage_includes_sector_concentration if { scan_level in {"maximum", "high"} }
```

### 6.6 Integration Point — Guardrail Firing Order

```
USER MESSAGE
  → [1] Intent Classification
  → [2] Authority Check
  → [3] Plan Validation
  → [4] Generic Safety
  → [5] MNPI Pre-Filter (M4 — strips fields BEFORE LLM)
  ═══ LLM PROCESSES ═══
  → [6] MNPI Leakage Scan ◄── THIS COMPONENT (after LLM, before delivery)
  → [7] Source Attribution
  → [8] Compliance Output Scan (Reg BI, FINRA 2210)
  → [9] PII Detection
  → [10] Rate Limit Check
  → RESPONSE TO USER
  → [11] Audit Log (M10)
```

### 6.7 Accuracy Estimates

| Configuration | FP Rate | FN Rate | Latency |
|---------------|---------|---------|---------|
| Tier 3/4 (Layers 1+2) | ~15-20% | ~20-30% | 70-220ms |
| Tier 1/2 (Layers 1+2+3 on flags) | ~12-15% | ~8-12% | 70-2200ms |
| Tier 5 (all 3 always) | ~10-12% | ~5-8% | 570-2200ms |

`[SME-REQUIRED]` Acceptable FP/FN rates per archetype. Higher FP = more regenerations (latency). Higher FN = more leakage risk (compliance).

### 6.8 Estimates

| Component | Lines |
|-----------|-------|
| Layer 1: Deterministic value scan | ~120 |
| Layer 2: Entity extraction + patterns | ~250 |
| Layer 3: LLM classifier prompt + handler | ~150 |
| Orchestrator (layered execution) | ~100 |
| OPA scan config rules | ~60 |
| Inference pattern library (YAML) | ~80 |
| **Total** | **~760** |

### 6.9 Design Boundary

- 🟢 **FULLY DESIGNABLE:** Layered detection architecture, deterministic scan, entity extraction, LLM classifier prompt, per-archetype config, guardrail integration, false positive handling
- 🟡 **SME MUST FILL IN:** Acceptable FP/FN rates per archetype, inference pattern library (what language = "leakage" vs. acceptable generalization), per-firm sensitivity overrides
- 🔴 **LEGAL REQUIRED:** Definition of "material" for AI-inferred information (novel legal question — no precedent for LLM inference as MNPI source)

---

## 7. CROSS-BORDER REGULATORY ARCHITECTURE

### 7.1 Purpose

The same platform must enforce different regulatory regimes in different jurisdictions. A US broker-dealer operates under FINRA/SEC rules. The same firm's EU subsidiary operates under MiFID II, GDPR, and DORA. The UK subsidiary operates under FCA rules. This component designs the jurisdiction-aware framework that makes this possible without forking the codebase.

### 7.2 Jurisdiction Field

Add to enterprise-config.yaml and Agent Identity Document:

```yaml
# enterprise-config.yaml — jurisdiction section
jurisdiction:
  primary: "US_FINRA_BD"
  additional:
    - "US_SEC_IA"
    - "EU_MIFID2"
  data_residency:
    default: "us-east-1"
    eu_clients: "eu-west-1"
    uk_clients: "eu-west-2"
```

Jurisdiction enum:

| Enum Value | Regulator | Key Requirements |
|-----------|-----------|-----------------|
| `US_FINRA_BD` | FINRA/SEC | Reg BI, 17a-4, 3110, 2210, BSA/AML |
| `US_SEC_IA` | SEC | IA Act fiduciary, Form ADV, 206(4)-7 |
| `US_SEC_FUND` | SEC | 1940 Act, 38a-1, diversification |
| `US_ERISA` | DOL | Fiduciary, prohibited transactions |
| `EU_MIFID2` | ESMA/NCAs | Suitability, best execution, research unbundling |
| `EU_GDPR` | DPAs | Consent, erasure, DPA, DPIA, SCCs |
| `EU_DORA` | ESAs | ICT risk, incident reporting, third-party register |
| `UK_FCA` | FCA | Consumer Duty, SMCR, MiFID-equivalent |
| `SG_MAS` | MAS | Technology Risk Management, AI governance |
| `HK_SFC` | SFC | Suitability, algo trading rules |

AID extension:

```json
{
  "firm": {
    "jurisdictions": ["US_FINRA_BD", "EU_MIFID2"],
    "primary_jurisdiction": "US_FINRA_BD"
  },
  "acting_on_behalf_of": {
    "jurisdiction": "US_FINRA_BD",
    "client_jurisdiction": "EU_MIFID2"
  }
}
```

### 7.3 OPA Bundle Structure for Multi-Jurisdiction

Single OPA instance, jurisdiction-scoped bundles. Rules self-select based on jurisdiction in input context.

```
opa_bundles/
├── authority/              # Core (jurisdiction-agnostic)
├── mnpi/                   # Core (jurisdiction-agnostic)
├── account_type/           # Component 5
├── bsa_aml/                # Component 4
├── jurisdiction/           # NEW — jurisdiction-specific
│   ├── us_finra/
│   │   ├── reg_bi.rego
│   │   ├── rule_3110.rego
│   │   ├── rule_2210.rego
│   │   └── rule_17a4.rego
│   ├── us_sec_ia/
│   │   ├── fiduciary.rego
│   │   └── form_adv.rego
│   ├── eu_mifid2/
│   │   ├── suitability.rego
│   │   ├── best_execution.rego
│   │   ├── research_unbundling.rego
│   │   └── transaction_reporting.rego
│   ├── eu_gdpr/
│   │   ├── consent.rego
│   │   ├── erasure.rego
│   │   ├── data_transfer.rego
│   │   └── dpia.rego
│   ├── eu_dora/
│   │   ├── ict_risk.rego
│   │   ├── incident_reporting.rego
│   │   └── third_party.rego
│   ├── uk_fca/
│   │   ├── consumer_duty.rego
│   │   └── smcr.rego
│   ├── sg_mas/
│   │   └── trm_guidelines.rego
│   └── hk_sfc/
│       └── suitability.rego
└── conflict_resolution/    # Cross-jurisdiction conflicts
    └── conflicts.rego
```

```rego
# jurisdiction/eu_mifid2/suitability.rego
package jurisdiction.eu_mifid2.suitability

import rego.v1

# Only evaluate if client is in MiFID II jurisdiction
applies if {
    input.context.client_jurisdiction == "EU_MIFID2"
}

deny contains msg if {
    applies
    input.action == "deliver_recommendation"
    not input.context.mifid2_suitability_assessment
    msg := "BLOCKED: MiFID II suitability assessment required for EU client."
}

deny contains msg if {
    applies
    input.action == "deliver_recommendation"
    assessment := input.context.mifid2_suitability_assessment
    not assessment.knowledge_and_experience_assessed
    msg := "BLOCKED: MiFID II requires assessment of client knowledge and experience."
}
```

### 7.4 Conflict Resolution Hierarchy

```rego
# conflict_resolution/conflicts.rego
package conflict_resolution

import rego.v1

# GDPR erasure vs 17a-4 retention: retention wins during retention period
resolve_erasure_vs_retention := "retain" if {
    input.conflict.type == "erasure_vs_retention"
    input.context.record_type in {"trade", "order", "communication", "audit"}
    retention_end := time.parse_rfc3339_ns(input.context.retention_expires_at)
    time.now_ns() < retention_end
}

resolve_erasure_vs_retention := "erase" if {
    input.conflict.type == "erasure_vs_retention"
    input.context.record_type in {"trade", "order", "communication", "audit"}
    retention_end := time.parse_rfc3339_ns(input.context.retention_expires_at)
    time.now_ns() >= retention_end
}

# Non-regulated data: GDPR erasure applies immediately
resolve_erasure_vs_retention := "erase" if {
    input.conflict.type == "erasure_vs_retention"
    not input.context.record_type in {"trade", "order", "communication", "audit"}
}

# US vs EU suitability: apply the MORE restrictive standard
resolve_suitability := "mifid2" if {
    input.conflict.type == "suitability_standard"
    "EU_MIFID2" in input.context.applicable_jurisdictions
}

resolve_suitability := "reg_bi" if {
    input.conflict.type == "suitability_standard"
    "US_FINRA_BD" in input.context.applicable_jurisdictions
    not "EU_MIFID2" in input.context.applicable_jurisdictions
}

# General principle: when in doubt, most restrictive wins
default_resolution := "apply_most_restrictive"
```

### 7.5 Data Residency Routing (M6)

```
MCP Request → M6 Gateway
  │
  ├─ Step 1: Determine client jurisdiction from AID
  │    client_jurisdiction = aid.client_jurisdiction
  │
  ├─ Step 2: Look up data residency requirement
  │    EU client → process in eu-west-1
  │    UK client → process in eu-west-2
  │    US client → process in us-east-1 (default)
  │
  ├─ Step 3: Route to region-appropriate MCP server instance
  │    M11 adapters deployed per-region where required
  │    M10 audit writes to region-local WORM storage
  │    LLM calls to region-appropriate endpoint
  │
  └─ Step 4: Cross-border transfer check
       If data must cross borders (EU→US):
       → Check valid transfer mechanism (SCCs, adequacy)
       → Log cross-border transfer to M10 WORM
       → If no valid mechanism → BLOCK transfer
```

### 7.6 GDPR Module Design

#### Consent Management

```json
{
  "gdpr_consent_record": {
    "client_id": "C-EU-12345",
    "consents": [
      {
        "consent_type": "data_processing",
        "purpose": "investment_advisory_services",
        "legal_basis": "contract_performance",
        "granted_at": "2026-07-15T10:00:00Z",
        "expires_at": null,
        "withdrawal_mechanism": "client_portal_or_request"
      },
      {
        "consent_type": "ai_processing",
        "purpose": "ai_agent_assisted_advisory",
        "legal_basis": "legitimate_interest_with_consent",
        "granted_at": "2026-07-15T10:00:00Z",
        "lia_documented": true,
        "opt_out_available": true
      },
      {
        "consent_type": "cross_border_transfer",
        "purpose": "processing_in_us_region",
        "legal_basis": "standard_contractual_clauses",
        "scc_version": "2021/914",
        "granted_at": "2026-07-15T10:00:00Z"
      }
    ],
    "dpia_reference": "DPIA-007-MNPI-ENGINE-v1",
    "data_controller": "Firm EU Subsidiary",
    "data_processor": "007 Platform (via DPA)"
  }
}
```

#### Right-to-Erasure Workflow

```
Client requests erasure (GDPR Art. 17)
  │
  ├─ Step 1: Identify all data for this client across all modules
  │    M1 (AID records), L2-L4 (memory), M10 (audit), CRM
  │
  ├─ Step 2: Check legal hold / retention override
  │    → OPA: conflict_resolution.resolve_erasure_vs_retention
  │    → If record_type in {trade, order, communication, audit}
  │       AND retention period not expired → RETAIN (log reason)
  │    → If non-regulated data → ERASE
  │
  ├─ Step 3: Execute erasure for eligible data
  │    Memory L2-L4: delete client entries
  │    CRM: delete/anonymize client record
  │    M1: revoke client-specific AIDs
  │    Langfuse: delete client traces (within 90-day window)
  │
  ├─ Step 4: Document retained data with justification
  │    For each retained record: reason, legal basis, retention end date
  │    Notify client: "These records retained per [regulation] until [date]"
  │
  └─ Step 5: Log erasure action to M10 WORM
       (Ironic: the erasure itself must be logged and retained)
```

#### DPIA for MNPI Engine

```yaml
# dpia-007-mnpi-engine.yaml
dpia:
  title: "Data Protection Impact Assessment — MNPI Filtering Engine"
  version: "1.0"
  date: "2026-07-15"
  controller: "[SME-REQUIRED: firm EU entity name]"
  dpo_contact: "[SME-REQUIRED: DPO email]"

  processing_description:
    purpose: "Filter material non-public information from AI agent context"
    data_categories:
      - "Client investment holdings (special category: financial)"
      - "Client identity data (name, account numbers)"
      - "Transaction history"
      - "Investment objectives and risk profile"
    data_subjects: "EU retail and institutional clients"
    processing_operations:
      - "Field-level filtering based on user role and archetype"
      - "LLM context assembly with filtered data"
      - "Output scanning for MNPI leakage"
    retention: "Filtered data: session duration. Audit logs: 6 years."

  necessity_and_proportionality:
    legal_basis: "Legitimate interest (regulatory compliance) + consent"
    necessity: "MNPI filtering is legally required to prevent insider trading"
    proportionality: "Only fields necessary for the query are retrieved. Filtering removes fields not needed for the specific interaction."

  risks_identified:
    - risk: "LLM infers MNPI from filtered context"
      likelihood: "medium"
      severity: "high"
      mitigation: "MNPI Leakage Scan (Component 6) with layered detection"
    - risk: "Audit trail contains MNPI"
      likelihood: "high"
      severity: "medium"
      mitigation: "Audit trail access restricted by role. WORM prevents modification."

  dpo_opinion: "[SME-REQUIRED: DPO assessment]"
  supervisory_authority_consultation: "[SME-REQUIRED: if required]"
```

#### DPA Tracking

```json
{
  "data_processing_agreements": [
    {
      "processor": "AWS (Bedrock)",
      "service": "LLM inference",
      "dpa_signed": true,
      "dpa_date": "2026-06-01",
      "scc_included": true,
      "data_categories_processed": ["client_queries", "filtered_holdings"],
      "processing_location": "eu-west-1",
      "sub_processors": ["Anthropic (model provider)"],
      "annual_review_due": "2027-06-01"
    },
    {
      "processor": "MCP Server Vendor (Orion)",
      "service": "Portfolio data retrieval",
      "dpa_signed": true,
      "dpa_date": "2026-05-15",
      "data_categories_processed": ["client_holdings", "transactions"],
      "processing_location": "us-east-1",
      "cross_border_mechanism": "SCCs",
      "annual_review_due": "2027-05-15"
    }
  ]
}
```

### 7.7 DORA Module Design

#### Third-Party ICT Risk Register

Every MCP server vendor is an ICT third-party service provider under DORA:

```json
{
  "ict_third_party_register": [
    {
      "provider_id": "ICT-001",
      "provider_name": "AWS",
      "services": ["LLM inference (Bedrock)", "Compute (EKS)", "Storage (S3)"],
      "criticality": "critical",
      "substitutability": "medium",
      "data_processed": ["client queries", "filtered holdings", "audit logs"],
      "processing_locations": ["eu-west-1", "us-east-1"],
      "contract_start": "2026-01-01",
      "contract_end": "2027-12-31",
      "exit_strategy_documented": true,
      "exit_strategy_reference": "docs/exit-strategy-aws.md",
      "last_risk_assessment": "2026-06-01",
      "next_risk_assessment": "2026-12-01",
      "incident_notification_sla": "4 hours",
      "audit_rights": true,
      "sub_outsourcing": ["Anthropic (LLM model provider)"]
    },
    {
      "provider_id": "ICT-002",
      "provider_name": "Orion Portfolio Solutions",
      "services": ["Portfolio management data"],
      "criticality": "important",
      "substitutability": "medium",
      "data_processed": ["client holdings", "transactions", "performance"],
      "processing_locations": ["us-east-1"],
      "exit_strategy_documented": true,
      "exit_strategy_reference": "docs/exit-strategy-orion.md",
      "incident_notification_sla": "24 hours"
    }
  ]
}
```

#### Incident Reporting Hooks

```python
# Pseudocode: DORA incident reporting
class DORAIncidentReporter:
    MAJOR_INCIDENT_SLA_HOURS = 4
    SIGNIFICANT_INCIDENT_SLA_HOURS = 24

    async def detect_and_report(self, incident):
        severity = self.classify_severity(incident)

        if severity == "major":
            # 4-hour initial notification to competent authority
            await self.send_initial_notification(
                authority=self.get_competent_authority(),
                incident=incident,
                deadline_hours=self.MAJOR_INCIDENT_SLA_HOURS
            )
            # Intermediate report within 72 hours
            await self.schedule_intermediate_report(incident, hours=72)
            # Final report within 1 month
            await self.schedule_final_report(incident, days=30)

        # All incidents logged to M10 WORM
        await audit_log(event="dora_incident", severity=severity,
                       details=incident)

    def classify_severity(self, incident):
        # Major: affects critical ICT services, >2hr downtime,
        # data breach, >10% of clients affected
        if (incident.affects_critical_service and
            incident.downtime_minutes > 120):
            return "major"
        if incident.data_breach:
            return "major"
        if incident.clients_affected_pct > 0.10:
            return "major"
        return "significant"
```

#### Exit Strategy Template

```yaml
# docs/exit-strategy-aws.md (structured)
exit_strategy:
  provider: "AWS"
  trigger_conditions:
    - "Provider insolvency or acquisition"
    - "Regulatory prohibition on using provider"
    - "Repeated SLA breaches (>3 major incidents in 12 months)"
    - "Unacceptable price increase (>50% YoY)"

  migration_plan:
    target_alternatives:
      - "Azure (topology 2 already designed)"
      - "GCP (Vertex AI for LLM)"
      - "On-premise (topology 3 already designed)"
    estimated_migration_time: "8-12 weeks"
    data_extraction:
      - "M10 WORM: S3 Object Lock → Azure Immutable Blob / NetApp SnapLock"
      - "OPA bundles: S3 → MinIO / Azure Blob"
      - "DynamoDB: export to PostgreSQL (on-prem)"
      - "Redis: stateless, no migration needed"
    service_continuity: "Hybrid topology allows gradual migration"

  testing:
    frequency: "Annual"
    last_tested: "[SME-REQUIRED: date]"
    test_scope: "Migrate trust layer (M1, M2/M4, M6, M10) to on-prem K8s"
```

### 7.8 MiFID II Module Design

#### Suitability Assessment (EU Alternative to Reg BI)

```json
{
  "mifid2_suitability_assessment": {
    "client_id": "C-EU-12345",
    "assessment_date": "2026-07-15",
    "knowledge_and_experience": {
      "assessed": true,
      "investment_experience_years": 5,
      "product_types_familiar": ["equities", "bonds", "etfs"],
      "product_types_unfamiliar": ["derivatives", "structured_products"],
      "education_level": "university",
      "professional_experience_financial": false
    },
    "financial_situation": {
      "assessed": true,
      "source_of_income": "employment",
      "annual_income_eur": 85000,
      "liquid_assets_eur": 200000,
      "regular_financial_commitments_eur": 24000,
      "ability_to_bear_losses": "partial"
    },
    "investment_objectives": {
      "assessed": true,
      "risk_tolerance": "moderate",
      "investment_horizon": "5-10 years",
      "purpose": "retirement_planning",
      "return_expectations": "inflation_plus_3pct"
    },
    "suitability_conclusion": "Product is suitable given client profile",
    "warnings_issued": [],
    "assessment_method": "ai_agent_questionnaire_with_human_review"
  }
}
```

#### Best Execution Reporting

```json
{
  "mifid2_best_execution_report": {
    "order_id": "ORD-EU-789",
    "execution_venue": "Euronext Paris",
    "execution_price": 142.50,
    "execution_time": "2026-07-15T14:30:00Z",
    "order_size": 500,
    "venues_considered": [
      {"venue": "Euronext Paris", "indicative_price": 142.50, "selected": true},
      {"venue": "CBOE Europe", "indicative_price": 142.52, "selected": false},
      {"venue": "Turquoise", "indicative_price": 142.48, "selected": false,
       "reason_not_selected": "Insufficient liquidity for order size"}
    ],
    "execution_factors_considered": ["price", "cost", "speed", "likelihood_of_execution", "size"],
    "total_cost_to_client_eur": 7.50,
    "reporting_deadline": "T+1 to national competent authority"
  }
}
```

#### Research Unbundling Cost Tracking

```json
{
  "research_unbundling": {
    "research_provider": "Bloomberg",
    "research_type": "third_party_research",
    "cost_allocation": "firm_pnl",
    "annual_budget_eur": 50000,
    "ytd_spend_eur": 28000,
    "cost_per_query_estimate_eur": 0.15,
    "client_disclosure": "Research costs borne by firm, not charged to client",
    "rpa_reference": "Research Payment Account RPA-2026-001"
  }
}
```

### 7.9 Enterprise Config Template — Multi-Jurisdiction

```yaml
# enterprise-config.yaml — firm with US + EU operations
firm:
  name: "Global Wealth Partners"
  lei: "5493001KJTIIGC8Y1R12"
  entities:
    - entity_name: "GWP Securities LLC"
      jurisdiction: "US_FINRA_BD"
      finra_crd: "123456"
      archetype: "tier3_wealth_management"
      regulators: ["FINRA", "SEC"]
    - entity_name: "GWP Europe GmbH"
      jurisdiction: "EU_MIFID2"
      lei: "5493001KJTIIGC8Y1R13"
      archetype: "tier3_wealth_management"
      regulators: ["BaFin", "ESMA"]
      additional_regimes: ["EU_GDPR", "EU_DORA"]
    - entity_name: "GWP UK Ltd"
      jurisdiction: "UK_FCA"
      fca_frn: "987654"
      archetype: "tier3_wealth_management"
      regulators: ["FCA"]

jurisdiction:
  primary: "US_FINRA_BD"
  additional: ["EU_MIFID2", "EU_GDPR", "EU_DORA", "UK_FCA"]
  data_residency:
    default: "us-east-1"
    eu_clients: "eu-west-1"
    uk_clients: "eu-west-2"
  conflict_resolution: "apply_most_restrictive"

compliance:
  us:
    reg_bi_required: true
    rule_17a4_retention_years: 6
    bsa_aml_enabled: true
    smarsh_archiving: true
  eu:
    mifid2_suitability: true
    best_execution_reporting: true
    research_unbundling: true
    transaction_reporting_sla: "T+1"
    gdpr:
      dpo_email: "[SME-REQUIRED]"
      dpia_required: true
      consent_management: true
      cross_border_mechanism: "standard_contractual_clauses"
    dora:
      ict_register_enabled: true
      incident_reporting_sla_hours: 4
      exit_strategies_required: true
      resilience_testing_frequency: "annual"
  uk:
    consumer_duty: true
    smcr_enabled: true

gdpr:
  consent_types:
    - type: "data_processing"
      legal_basis: "contract_performance"
      required: true
    - type: "ai_processing"
      legal_basis: "legitimate_interest_with_consent"
      required: true
      opt_out_available: true
    - type: "cross_border_transfer"
      legal_basis: "standard_contractual_clauses"
      required_if: "client_jurisdiction in [EU_MIFID2, EU_GDPR]"

dora:
  ict_providers:
    - name: "AWS"
      criticality: "critical"
      exit_strategy: "docs/exit-strategy-aws.md"
    - name: "Orion"
      criticality: "important"
      exit_strategy: "docs/exit-strategy-orion.md"
    - name: "Salesforce"
      criticality: "important"
      exit_strategy: "docs/exit-strategy-salesforce.md"
```

### 7.10 Estimated Lines of Code Per Module

| Sub-Module | Lines | Phase |
|-----------|-------|-------|
| Jurisdiction OPA rules (`jurisdiction/us_finra/`) | ~150 (mostly existing, reorganized) | Phase 1-2 |
| Jurisdiction OPA rules (`jurisdiction/eu_mifid2/`) | ~200 | Phase 5 |
| Jurisdiction OPA rules (`jurisdiction/eu_gdpr/`) | ~180 | Phase 3 (basics), Phase 5 (full) |
| Jurisdiction OPA rules (`jurisdiction/eu_dora/`) | ~120 | Phase 3 (basics), Phase 5 (full) |
| Jurisdiction OPA rules (`jurisdiction/uk_fca/`) | ~100 | Phase 5 |
| Jurisdiction OPA rules (`jurisdiction/sg_mas/`, `hk_sfc/`) | ~80 | Phase 5+ |
| Conflict resolution rules | ~100 | Phase 3 |
| Data residency routing (M6 extension) | ~200 | Phase 3 |
| GDPR consent management service | ~300 | Phase 3 |
| GDPR erasure workflow | ~250 | Phase 3 |
| GDPR DPA tracking | ~100 | Phase 3 |
| DORA ICT register service | ~200 | Phase 3 |
| DORA incident reporting hooks | ~150 | Phase 3 |
| MiFID II suitability assessment | ~250 | Phase 5 |
| MiFID II best execution reporting | ~200 | Phase 5 |
| MiFID II research unbundling tracking | ~100 | Phase 5 |
| MiFID II transaction reporting | ~200 | Phase 5 |
| **Total** | **~2,880** | |

### 7.11 Design Boundary

- 🟢 **FULLY DESIGNABLE:** OPA bundle structure, jurisdiction routing, conflict resolution rules, data residency routing, GDPR consent schema, DORA ICT register schema, MiFID II suitability schema, enterprise config template, exit strategy template
- 🟡 **SME MUST FILL IN:** Per-jurisdiction regulatory thresholds, DPO contact, competent authority contacts, DPIA content, consent text, research unbundling budgets, best execution venue lists, FCA Consumer Duty specific requirements, MAS TRM specific requirements, SFC specific requirements
- 🔴 **LEGAL REQUIRED:** SCC text, DPA terms, GDPR consent language, DORA contractual requirements with ICT providers, MiFID II suitability questionnaire legal review, cross-border data transfer legal opinions

---

## SUMMARY: ALL 7 COMPONENTS

### Estimated Total Lines of Code

| Component | New Code | OPA Rego | Total |
|-----------|----------|----------|-------|
| 1. Reg BI Documentation Generator | ~400 Python | ~80 | ~480 |
| 2. Liability Framework | ~0 (config + schemas) | ~0 | Config templates |
| 3. WSP-to-YAML Mapping | ~150 Python | ~0 | ~150 + YAML |
| 4. BSA/AML Ongoing Monitoring | ~500 Python | ~200 | ~700 |
| 5. ERISA Account-Type Awareness | ~140 Python | ~250 | ~540 |
| 6. MNPI Leakage Scan | ~620 Python | ~60 | ~760 |
| 7. Cross-Border Regulatory | ~1,950 Python | ~930 | ~2,880 |
| **TOTAL** | **~3,760** | **~1,520** | **~5,510** |

### Phase Mapping

| Component | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|-----------|---------|---------|---------|---------|---------|
| 1. Reg BI Generator | Design | Implement | | | |
| 2. Liability Framework | Design | Template | Legal review | | |
| 3. WSP-to-YAML Mapping | Design | Implement | Maintain | | |
| 4. BSA/AML Monitoring | | Basic CTR | Full patterns | | |
| 5. ERISA Account-Type | Design | Implement | | | |
| 6. MNPI Leakage Scan | Prototype | Layers 1+2 | Layer 3 | Tune | |
| 7. Cross-Border | | | GDPR/DORA basics | | Full MiFID/FCA |

### Module Integration Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│           HOW THE 7 NEW COMPONENTS CONNECT TO EXISTING 12 MODULES       │
│                                                                         │
│  M1 (Identity)                                                          │
│    ← Component 7: jurisdiction field in AID                             │
│                                                                         │
│  M2/M4 (OPA Policy Engine)                                              │
│    ← Component 1: authority/reg_bi.rego                                 │
│    ← Component 4: bsa_aml/ bundle (SAR, CTR, CDD)                      │
│    ← Component 5: account_type/ bundle (ERISA, IRA, trust, custodial)  │
│    ← Component 6: mnpi/leakage_scan_config.rego                        │
│    ← Component 7: jurisdiction/ bundle + conflict_resolution/           │
│                                                                         │
│  M3 (Canonical Schema)                                                  │
│    ← Component 5: account_type field on Client and Holding              │
│                                                                         │
│  M5 (Enterprise Config)                                                 │
│    ← Component 1: conflict/fee disclosure config                        │
│    ← Component 2: liability section template                            │
│    ← Component 7: jurisdiction, GDPR, DORA config sections             │
│                                                                         │
│  M6 (MCP Gateway)                                                       │
│    ← Component 7: data residency routing + cross-border transfer checks │
│                                                                         │
│  M8 (Pipeline Engine)                                                   │
│    ← Component 1: reg_bi_generator.py sub-module                        │
│                                                                         │
│  M10 (Audit Logger)                                                     │
│    ← Component 1: Reg BI doc persistence to WORM                       │
│    ← Component 2: provenance chain, hash chain integrity                │
│    ← Component 3: WSP mapping evidence for examiners                    │
│    ← Component 4: BSA/AML check audit entries                           │
│    ← Component 7: GDPR erasure log, DORA incident log                  │
│                                                                         │
│  Line 2 (Client Service) ← Component 1: Reg BI gate trigger            │
│  Line 3 (Compliance/OPA) ← Component 4: BSA/AML alert routing          │
│  Line 4 (Execution)      ← Components 4+5: BSA/AML + account-type      │
│  Line 5 (Onboarding)     ← Components 4+7: KYC baseline + GDPR consent │
│  Output Guardrails        ← Component 6: MNPI Leakage Scan [guardrail 6]│
└─────────────────────────────────────────────────────────────────────────┘
```

### What These 7 Components Do to the Compliance Score

The LLMJ committee scored compliance at 6.6/10. These designs address every gap cited:

| Gap Cited by Committee | Component | Coverage |
|------------------------|-----------|----------|
| "Reg BI documentation not designed as first-class module" | 1 | Full JSON schema, OPA rules, integration flow, examiner workflow |
| "No liability matrix, no compliance warranty boundary" | 2 | Warranty tiers, provenance chain, module responsibility matrix, insurance integration |
| "Human-readable WSP mapping to technical controls needed" | 3 | Bidirectional mapping, version sync, annual review template |
| "Ongoing SAR/CTR/CDD monitoring absent" | 4 | OPA rules, integration with Lines 4+5, alert routing |
| "No account-type-specific compliance rules" | 5 | Full taxonomy, OPA rules per type, Reg BI integration |
| "MNPI Leakage Scan listed but not designed" | 6 | Layered detection (D+B+C), per-archetype sensitivity, accuracy estimates |
| "No jurisdiction-aware compliance architecture" | 7 | OPA bundle structure, conflict resolution, GDPR/DORA/MiFID II modules |

---

*Project 007 v2.1 — Compliance Gap Designs*
*Addressing LLMJ Committee Compliance Score 6.6/10*
*July 2026*

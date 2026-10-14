# PROJECT 007 v3 — COMPLIANCE GAP TECHNICAL DESIGNS

> Version: 3.0
> Date: July 2026
> Status: Detailed Technical Design for 7 Compliance Gaps (addressing LLMJ Committee v2 Reassessment §4.1–4.2)
> Audience: Engineering team, compliance SME, architecture review board
> Predecessor: v2 architecture (3 documents), LLMJ Committee v2 Reassessment
> Scope: Gaps 1–5 from §4.1 (Compliance Gaps) + Gaps 6–7 from §4.2 (Architectural Gaps)

---

## TABLE OF CONTENTS

1. [GAP 1: Reg BI Documentation Generator](#gap-1-reg-bi-documentation-generator)
2. [GAP 2: Liability Framework](#gap-2-liability-framework)
3. [GAP 3: WSP-to-YAML Mapping](#gap-3-wsp-to-yaml-mapping)
4. [GAP 4: BSA/AML Ongoing Monitoring](#gap-4-bsaaml-ongoing-monitoring)
5. [GAP 5: ERISA Account-Type Awareness](#gap-5-erisa-account-type-awareness)
6. [GAP 6: MNPI Leakage Scan](#gap-6-mnpi-leakage-scan)
7. [GAP 7: Cross-Border Regulatory Architecture](#gap-7-cross-border-regulatory-architecture)

---
---

## GAP 1: REG BI DOCUMENTATION GENERATOR

### 1.1 Regulatory Context

Regulation Best Interest (SEC Rule 15l-1, effective June 2020) imposes four obligations on broker-dealers when making recommendations to retail customers:

| Obligation | Requirement | Agent Mapping |
|------------|-------------|---------------|
| **Disclosure** | Deliver Form CRS; disclose material facts about the relationship, fees, conflicts | Agent surfaces applicable disclosures at recommendation time |
| **Care** | Exercise reasonable diligence, care, and skill; consider alternatives; ensure recommendation is in client's best interest | Agent documents the reasoning chain: why this recommendation, what alternatives, why best for THIS client |
| **Conflict of Interest** | Establish policies to identify, disclose, and mitigate conflicts | Agent flags known conflicts from the firm's conflict inventory |
| **Compliance** | Establish, maintain, and enforce written policies and procedures | The Reg BI doc generator IS part of the compliance obligation — it proves the other three are met |

### 1.2 Module Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REG BI DOCUMENTATION GENERATOR                       │
│                    (Sub-module of M10 Audit Logger)                     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  TRIGGER DETECTION LAYER                                        │   │
│  │  Listens on inter-agent message bus for recommendation events   │   │
│  │                                                                 │   │
│  │  Triggers:                                                      │   │
│  │  • Client Service Specialist → "recommendation" intent          │   │
│  │  • Research Specialist → ResearchBrief with rating/action       │   │
│  │  • Execution Specialist → Order enters DRAFT state              │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CONTEXT ASSEMBLER                                              │   │
│  │  Gathers all data needed to populate the Reg BI document:       │   │
│  │  • Client profile (M3 canonical Client)                         │   │
│  │  • Current holdings (M3 canonical Holding[])                    │   │
│  │  • Recommendation details (security, action, quantity, reason)  │   │
│  │  • Alternatives considered (from LLM reasoning trace / Langfuse)│   │
│  │  • Conflict inventory (from enterprise config — firm-level)     │   │
│  │  • Cost data (commissions, fees, expense ratios)                │   │
│  │  • Account type (taxable, IRA, 401k — feeds into GAP 5)        │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  DOCUMENT GENERATOR                                             │   │
│  │  Populates the Reg BI document from template + assembled context│   │
│  │                                                                 │   │
│  │  Mode A: Deterministic fields (client profile, costs, conflicts)│   │
│  │          → populated from structured data, NO LLM               │   │
│  │  Mode B: Narrative fields (basis for recommendation, why best   │   │
│  │          interest, alternatives analysis)                       │   │
│  │          → LLM-generated from reasoning trace, Haiku model      │   │
│  │          → HITL review required before finalization              │   │
│  └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  STORAGE + RETRIEVAL                                            │   │
│  │  • CRM: RegBIDocument linked to client + recommendation         │   │
│  │  • WORM: S3 Object Lock (immutable, 6-year retention)           │   │
│  │  • Index: by client_id, advisor_id, date, security_id           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Output Schema: RegBIDocument

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RegBIDocument",
  "type": "object",
  "required": [
    "document_id", "version", "created_at", "firm_id",
    "advisor", "client", "recommendation", "obligations"
  ],
  "properties": {
    "document_id": { "type": "string", "format": "uuid" },
    "version": { "type": "string", "const": "1.0.0" },
    "created_at": { "type": "string", "format": "date-time" },
    "finalized_at": {
      "type": ["string", "null"], "format": "date-time",
      "description": "Null until advisor reviews and finalizes"
    },
    "status": {
      "type": "string",
      "enum": ["DRAFT", "PENDING_REVIEW", "FINALIZED", "SUPERSEDED"]
    },
    "firm_id": { "type": "string" },
    "advisor": {
      "type": "object",
      "required": ["user_id", "crd_number", "aid_hash"],
      "properties": {
        "user_id": { "type": "string" },
        "name": { "type": "string" },
        "crd_number": { "type": "string" },
        "aid_hash": { "type": "string", "description": "SHA-256 of AID at recommendation time" }
      }
    },
    "client": {
      "type": "object",
      "required": ["client_id", "risk_tolerance", "investment_objectives", "time_horizon", "account_type"],
      "properties": {
        "client_id": { "type": "string" },
        "name": { "type": "string" },
        "risk_tolerance": {
          "type": "string",
          "enum": ["conservative", "moderate_conservative", "moderate", "moderate_aggressive", "aggressive"]
        },
        "investment_objectives": {
          "type": "array",
          "items": { "type": "string", "enum": ["growth", "income", "capital_preservation", "speculation", "balanced"] }
        },
        "time_horizon": { "type": "string", "enum": ["short_term", "medium_term", "long_term"] },
        "annual_income_range": { "type": "string" },
        "net_worth_range": { "type": "string" },
        "liquid_net_worth_range": { "type": "string" },
        "account_type": { "type": "string" }
      }
    },
    "recommendation": {
      "type": "object",
      "required": ["type", "securities", "summary"],
      "properties": {
        "type": { "type": "string", "enum": ["buy", "sell", "hold", "switch", "rebalance", "allocation_change"] },
        "securities": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "ticker": { "type": "string" },
              "name": { "type": "string" },
              "security_type": { "type": "string" },
              "action": { "type": "string", "enum": ["buy", "sell", "hold"] },
              "quantity": { "type": ["number", "null"] },
              "estimated_value": { "type": ["number", "null"] }
            }
          }
        },
        "summary": { "type": "string" }
      }
    },
    "obligations": {
      "type": "object",
      "required": ["disclosure", "care", "conflict_of_interest", "compliance"],
      "properties": {
        "disclosure": {
          "type": "object",
          "required": ["form_crs_delivered", "fee_schedule_disclosed"],
          "properties": {
            "form_crs_delivered": { "type": "boolean" },
            "form_crs_delivery_date": { "type": ["string", "null"], "format": "date" },
            "material_facts_disclosed": { "type": "array", "items": { "type": "string" } },
            "fee_schedule_disclosed": { "type": "boolean" },
            "compensation_structure_disclosed": { "type": "boolean" }
          }
        },
        "care": {
          "type": "object",
          "required": ["basis_for_recommendation", "alternatives_considered", "best_interest_rationale", "risk_factors", "cost_analysis"],
          "properties": {
            "basis_for_recommendation": {
              "type": "string",
              "description": "Narrative: why this recommendation is appropriate for this client"
            },
            "alternatives_considered": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "properties": {
                  "description": { "type": "string" },
                  "reason_not_selected": { "type": "string" }
                }
              }
            },
            "best_interest_rationale": {
              "type": "string",
              "description": "Why this is in the client's best interest considering costs, risks, rewards"
            },
            "risk_factors": { "type": "array", "items": { "type": "string" } },
            "cost_analysis": {
              "type": "object",
              "required": ["total_estimated_cost"],
              "properties": {
                "estimated_commission": { "type": ["number", "null"] },
                "estimated_fees": { "type": ["number", "null"] },
                "expense_ratio": { "type": ["number", "null"] },
                "total_estimated_cost": { "type": "number" },
                "cost_comparison_to_alternatives": { "type": "string" }
              }
            }
          }
        },
        "conflict_of_interest": {
          "type": "object",
          "required": ["conflicts_identified"],
          "properties": {
            "conflicts_identified": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "conflict_type": { "type": "string", "enum": ["revenue_sharing", "proprietary_product", "compensation_incentive", "principal_trading", "other"] },
                  "description": { "type": "string" },
                  "mitigation": { "type": "string" }
                }
              }
            },
            "no_conflicts_attestation": { "type": "boolean" }
          }
        },
        "compliance": {
          "type": "object",
          "required": ["compliance_checks_passed", "restricted_list_clear"],
          "properties": {
            "compliance_checks_passed": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "check_type": { "type": "string" },
                  "result": { "type": "string", "enum": ["PASS", "WARN", "FAIL"] },
                  "rule_applied": { "type": "string" },
                  "details": { "type": "string" }
                }
              }
            },
            "restricted_list_clear": { "type": "boolean" },
            "concentration_check": { "type": "string" },
            "suitability_score": { "type": ["number", "null"] }
          }
        }
      }
    },
    "source_trace": {
      "type": "object",
      "required": ["trace_id", "specialist"],
      "properties": {
        "trace_id": { "type": "string" },
        "specialist": { "type": "string" },
        "pipeline_stage": { "type": ["string", "null"] },
        "langfuse_trace_url": { "type": ["string", "null"] },
        "data_sources_used": { "type": "array", "items": { "type": "string" } }
      }
    },
    "audit": {
      "type": "object",
      "required": ["worm_record_id", "sha256_hash"],
      "properties": {
        "worm_record_id": { "type": "string" },
        "sha256_hash": { "type": "string" },
        "crm_record_id": { "type": ["string", "null"] }
      }
    }
  }
}
```


### 1.4 Integration Points

```
TRIGGER SOURCES:

  Client Service Specialist ──┐
  (recommends action to       │
   advisor during meeting      │    ┌──────────────────────────┐
   prep or conversation)      ├───▶│  REG BI DOC GENERATOR    │
                              │    │                          │
  Research Specialist ────────┤    │  Assembles context from: │
  (ResearchBrief contains     │    │  • M3 canonical Client   │
   BUY/SELL/HOLD rating)      │    │  • M3 canonical Holding[]│
                              │    │  • Langfuse trace        │
  Execution Specialist ───────┘    │  • M5 enterprise config  │
  (Order enters DRAFT state,      │    (conflict inventory)   │
   pre-HITL gate)                  │  • M2/M4 compliance check│
                                   │    results               │
                                   └──────────┬───────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                         ┌────────┐    ┌──────────┐    ┌──────────┐
                         │  CRM   │    │  WORM    │    │ Advisor  │
                         │ Record │    │ Archive  │    │ Review   │
                         │(M10 T3)│    │(M10 T2)  │    │  Queue   │
                         └────────┘    └──────────┘    └──────────┘
```

**Trigger Detection Logic (pseudocode):**

```python
REG_BI_TRIGGER_INTENTS = {
    "client.recommend_action",
    "client.suggest_rebalance",
    "client.propose_allocation",
    "execution.prepare_order",
    "research.brief_with_rating",
}

async def should_generate_reg_bi(
    message: InterAgentMessage,
    aid: AgentIdentityDocument,
    enterprise_config: EnterpriseConfig,
) -> bool:
    # Reg BI does not apply to institutional clients
    if aid.archetype in ("tier1_investment_bank", "tier2_asset_manager"):
        return False
    # Pure RIAs have fiduciary duty, not Reg BI
    if enterprise_config.registration_type == "ria_only":
        return False
    # Dual-registered or BD: Reg BI applies to retail recommendations
    if message.intent in REG_BI_TRIGGER_INTENTS:
        return True
    if message.payload.get("recommended_action") is not None:
        return True
    return False
```

### 1.5 Template System

Firms have different Reg BI documentation formats. The template system supports firm-specific customization via Jinja2:

```yaml
# enterprise-config.yaml — Reg BI section
reg_bi:
  enabled: true
  registration_type: "dual_registered"  # bd_only | ria_only | dual_registered
  template: "default"                    # default | custom
  custom_template_path: null             # path to firm-specific Jinja2 template
  conflict_inventory:
    - type: "revenue_sharing"
      description: "Firm receives revenue sharing from XYZ Fund Family"
      mitigation: "Disclosed in Form CRS and account opening documents"
    - type: "proprietary_product"
      description: "Firm-managed model portfolios generate advisory fees"
      mitigation: "Fee comparison provided; non-proprietary alternatives offered"
  auto_generate: true
  require_advisor_review: true           # HITL: advisor must review before finalization
  narrative_model: "haiku"               # LLM model for narrative fields
  cost_data_source: "morningstar"        # source for expense ratios and fee data
```

### 1.6 FINRA Examiner Retrieval

A FINRA examiner requests: "Show me the Reg BI documentation for all recommendations made to client Henderson in Q2 2026."

```
RETRIEVAL FLOW:

  Examiner Request
       │
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  COMPLIANCE DASHBOARD (Grafana / Custom UI)          │
  │                                                      │
  │  Query: client_id = "C-12345"                        │
  │         AND created_at BETWEEN '2026-04-01'          │
  │                            AND '2026-06-30'          │
  │                                                      │
  │  Source 1: CRM (Salesforce) — business-accessible    │
  │  Source 2: WORM (S3 Object Lock) — regulatory record │
  │                                                      │
  │  For each document:                                  │
  │  • Verify SHA-256 hash matches WORM copy             │
  │  • Display all 4 obligation sections                 │
  │  • Link to Langfuse trace for full reasoning chain   │
  │  • Show advisor review timestamp and approval        │
  └──────────────────────────────────────────────────────┘

WORM Index Structure (S3 key pattern):
  s3://007-worm-audit/{firm_id}/reg-bi/{year}/{month}/{document_id}.json
```

### 1.7 What the Compliance SME Must Provide vs. What Is Automated

| Deliverable | Owner | Description |
|-------------|-------|-------------|
| Conflict inventory per firm | **Compliance SME** | List of all material conflicts (revenue sharing, proprietary products, compensation structures) |
| Reg BI field requirements per firm | **Compliance SME** | Which fields are required vs. optional for this firm's registration type |
| Suitability scoring methodology | **Compliance SME** | How to compute the suitability score — factors, weights, thresholds |
| Alternative consideration criteria | **Compliance SME** | What constitutes a "reasonable alternative" — minimum number, categories |
| Cost data source mapping | **Compliance SME** | Which vendor provides expense ratios, commission schedules, fee data |
| Custom template (if needed) | **Compliance SME** | Firm-specific Reg BI document format (Jinja2 template) |
| Trigger detection logic | **Automated** | Detects recommendation events from specialist messages |
| Context assembly | **Automated** | Gathers client profile, holdings, costs from canonical types |
| Deterministic field population | **Automated** | Client data, costs, compliance check results, conflict inventory |
| Narrative generation | **Automated (LLM)** | Basis for recommendation, best interest rationale, alternatives analysis — from reasoning trace |
| WORM archival | **Automated** | Immutable storage with SHA-256 integrity hash |
| CRM record creation | **Automated** | Salesforce RegBIDocument__c record linked to client and recommendation |
| Retrieval API | **Automated** | Query by client, advisor, date range, security |

### 1.8 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~800 Python (trigger + assembler + generator + storage) + ~200 Jinja2 templates + ~100 JSON Schema |
| **Modules Affected** | M10 (primary — sub-module), M3 (schema: RegBIDocument type), M5 (config: conflict inventory), M8 (pipeline: trigger on research brief), M12 (specialists: trigger on recommendation) |
| **SME Deliverables** | Conflict inventory, field requirements, suitability methodology, alternative criteria, cost source mapping |
| **Buildable Without SME** | Trigger detection, context assembly, WORM archival, CRM integration, retrieval API, template engine |
| **Implementation Phase** | Phase 2 (Weeks 12–28) — required before lighthouse deployment to any BD or dual-registered RIA |


---
---

## GAP 2: LIABILITY FRAMEWORK

### 2.1 Purpose

Every general counsel will ask before signing: "When the agent makes a mistake, who is liable?" This gap designs the technical infrastructure that makes liability traceable — not the legal terms themselves (that requires counsel), but the data capture, provenance chain, error attribution, and documentation that supports liability allocation.

### 2.2 Compliance Warranty Boundary

Every function in the system is classified as either **deterministic (warranted accurate)** or **probabilistic (best-effort)**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLIANCE WARRANTY BOUNDARY                         │
│                                                                         │
│  WARRANTED ACCURATE (Deterministic)                                    │
│  Platform warrants correct output given correct input data.            │
│  Errors here are platform defects.                                     │
│                                                                         │
│  • M1: AID issuance/verification/revocation                            │
│  • M2: Authority policy evaluation (OPA/Rego)                          │
│  • M3: Schema validation                                               │
│  • M4: MNPI field filtering (OPA/Rego)                                 │
│  • M5: Config loading and validation                                   │
│  • M7: Schema translation (field mapping — deterministic code)         │
│  • M10: Audit write (WORM integrity, SHA-256 hashing)                  │
│  • Compliance Specialist: All OPA rule evaluations                     │
│  • Execution Specialist: Order state machine transitions               │
│  • HITL gate enforcement: Gate cannot be bypassed                      │
│                                                                         │
│  BEST-EFFORT (Probabilistic — LLM-dependent)                          │
│  Platform does NOT warrant accuracy of LLM output.                     │
│  HITL gates exist to catch LLM errors before delivery.                 │
│                                                                         │
│  • M8: Research pipeline synthesis (LLM-generated analysis)            │
│  • M9: Intent classification (LLM function calling)                    │
│  • Client Service Specialist: Conversational responses                 │
│  • Research Specialist: Brief generation, financial analysis           │
│  • Onboarding Specialist: Document extraction, form filling            │
│  • Reg BI narrative fields (basis, rationale, alternatives)            │
│  • Memory L4/L5: Semantic/procedural memory (learned facts)            │
│                                                                         │
│  SHARED LIABILITY (Platform + Vendor)                                  │
│  Accuracy depends on both platform logic AND vendor data quality.      │
│                                                                         │
│  • M7: Semantic interpretation (e.g., Orion MarketValue definition)    │
│  • M11: MCP adapter data retrieval (vendor API correctness)            │
│  • M6: Gateway routing (correct MCP server selection)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Provenance Chain

For any agent output, trace back through every module that touched the data:

```
PROVENANCE CHAIN — Example: "Henderson meeting prep brief"

  OUTPUT: Meeting prep brief delivered to Sarah on Slack
  trace_id: "trace-abc-123" | output_hash: "sha256:9f3a..."
       │
       ▼
  STAGE 6: LLM Synthesis
  model: claude-haiku-4-20250514 | model_version: "bedrock:us-east-1:2025-05-14"
  input_hash: "sha256:7b2c..." | output_hash: "sha256:9f3a..."
  prompt_template_version: "client_service/meeting_prep:v2.3"
  temperature: 0.0 | tokens_in: 8432 | tokens_out: 1205 | latency_ms: 2340
       │
       ▼
  STAGE 5: MNPI Filter (M4)
  policy_bundle: "mnpi/v1.4.2" | rule: "mnpi/tier3_wealth_management.rego"
  fields_stripped: ["client.ssn", "client.dob"]
  fields_retained: ["holdings.*", "plan_summary.*"]
       │
       ▼
  STAGE 4: Schema Translation (M7)
  translator: "orion_position_to_holding:v1.2.0"
  canonical_schema: "Holding:v2.1.0" | source_system: "orion"
  semantic_notes: "MarketValue includes accrued interest"
       │
       ▼
  STAGE 3: MCP Server Response (M11)
  mcp_server: "orion-portfolio-adapter:v1.0.3"
  tool_called: "get_client_holdings" | vendor_api: "Orion REST API v2"
       │
       ▼
  STAGE 2: Authority Check (M2)
  policy_bundle: "authority/v1.6.0" | rule: "authority/client_access.rego"
  decision: "ALLOW" | input: {aid: "sarah.chen", action: "read", target: "C-12345"}
       │
       ▼
  STAGE 1: Identity Verification (M1)
  aid_hash: "sha256:e4c1..." | user: "sarah.chen@acmewm.com"
  archetype: "tier3_wealth_management" | role: "advisor"
```

**Provenance Record Schema (stored in WORM per trace_id):**

```json
{
  "trace_id": "trace-abc-123",
  "timestamp": "2026-07-15T14:30:00Z",
  "stages": [
    {
      "stage_number": 1,
      "module": "M1",
      "operation": "identity_verification",
      "version": "1.2.0",
      "input_hash": null,
      "output_hash": "sha256:e4c1...",
      "metadata": { "user": "sarah.chen@acmewm.com", "archetype": "tier3" },
      "latency_ms": 12,
      "warranty_category": "deterministic"
    }
  ],
  "final_output_hash": "sha256:9f3a...",
  "worm_record_id": "s3://007-worm-audit/acme_wm/provenance/2026/07/trace-abc-123.json"
}
```

### 2.4 Error Attribution Taxonomy

When something goes wrong, the system classifies the error source:

| Category | Liable Party | Detection Method | Evidence Captured |
|----------|-------------|------------------|-------------------|
| **1. Source Data Error** | Vendor | Schema reconciliation test failure | Vendor API response hash, canonical output hash, reconciliation result |
| **2. Schema Translation Error** | Platform | Reconciliation test, manual review | Translator version, schema version, input/output pair, mapping YAML |
| **3. Policy Evaluation Error** | Platform | Compliance audit, adversarial test failure | Policy bundle version + hash, OPA decision log, bundle propagation timestamp |
| **4. LLM Synthesis Error** | LLM Provider / Shared | Advisor review (HITL), output guardrail, anti-fabrication check | Model version, prompt input_hash, output, temperature, Langfuse trace |
| **5. Human Approval Error** | Firm / User | Post-hoc review, client complaint | HITL approval token (tamper-proof hash), approver AID, timestamp, output hash |
| **6. Compliance Rule Error** | SME / Firm | Regulatory examination, compliance audit | Rule version history, SME approval record, rule change audit trail |

### 2.5 Indemnification Data Capture

At every stage, the following is captured and stored in WORM:

| Stage | Data Captured | Purpose |
|-------|---------------|---------|
| M1 Identity | AID hash, user identity, archetype, role, token timestamps | Prove WHO made the request |
| M2 Authority | Policy bundle version + hash, rule applied, decision, input data | Prove authorization was correct per rules |
| M4 MNPI Filter | Policy bundle version, fields stripped/retained, input/output hashes | Prove MNPI was properly filtered |
| M6 Gateway | MCP server called, request/response hashes, latency, circuit breaker state | Prove correct data source was used |
| M7 Translation | Translator version, schema version, mapping hash, input/output hashes | Prove translation was correct per mapping |
| M8 Pipeline | Stage number, model version, prompt template version, input/output hashes | Prove LLM was called with correct parameters |
| M10 Audit | WORM record ID, SHA-256 integrity hash, write timestamp | Prove record is immutable and complete |
| HITL Gate | Approver AID, approval token, timestamp, output hash | Prove a human reviewed and approved |

### 2.6 Insurance Documentation Package

What the platform provides to an E&O insurance underwriter:

| Section | Contents |
|---------|----------|
| **System Architecture** | v2 tech stack doc, multi-agent doc, this gap designs doc, deployment topology |
| **Accuracy Metrics** | OPA: 99.9%. Schema reconciliation: <0.1% error. HITL enforcement: 100%. LLM intent: 85-95%. LLM synthesis: requires HITL review. |
| **HITL Enforcement Proof** | Execution: mandatory gate. Research: 3 gates. Reg BI: advisor review. All gates in WORM with tamper-proof tokens. |
| **Audit Trail Completeness** | Three-tier (Langfuse + S3 Object Lock + CRM). SHA-256 hashing. 6-year retention. Third-party access. Provenance chain. |
| **Warranty Boundary** | Warranted: deterministic checks, MNPI filtering, audit integrity. Not warranted: LLM output accuracy. Mitigation: HITL gates. |

### 2.7 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~400 Python (provenance chain recorder + error classifier) + ~200 JSON Schema + ~100 YAML config |
| **Modules Affected** | ALL modules (every module writes to provenance chain). Primary: M10 (storage), M6 (per-call capture), M8 (per-stage capture) |
| **SME Deliverables** | Liability allocation matrix (with legal counsel), warranty boundary sign-off, indemnification clause templates, E&O broker engagement |
| **Buildable Without SME** | Provenance chain recorder, error taxonomy, indemnification data capture, WORM storage, insurance doc template |
| **Implementation Phase** | Phase 1 (provenance chain — Weeks 4–16, built into M6/M10 from day one) + Phase 2 (liability docs — Weeks 12–28, before lighthouse LOIs) |


---
---

## GAP 3: WSP-TO-YAML MAPPING

### 3.1 Regulatory Context

FINRA Rule 3110 requires every broker-dealer to establish and maintain Written Supervisory Procedures (WSPs). A FINRA examiner will ask: "Show me your written supervisory procedures for this AI agent." The YAML/Rego config is not a WSP — it is a technical implementation. A human-readable WSP document that maps bidirectionally to the technical controls is required.

### 3.2 Module Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WSP-TO-YAML MAPPING SYSTEM                           │
│                                                                         │
│  ┌─────────────────────┐          ┌─────────────────────┐              │
│  │  HUMAN-READABLE     │◄────────▶│  MACHINE-READABLE   │              │
│  │  WSP DOCUMENTS      │  bidir.  │  OPA/REGO RULES     │              │
│  │  (Markdown/PDF)     │  mapping │  (Policy Bundles)   │              │
│  └──────────┬──────────┘          └──────────┬──────────┘              │
│             │                                │                          │
│             ▼                                ▼                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  CROSS-REFERENCE REGISTRY                                       │  │
│  │  Maps: WSP Section → OPA Policy Bundle → Rego Rule → Test Case  │  │
│  │  Stored in: Git (version-controlled YAML)                       │  │
│  │  Indexed by: WSP section number, policy bundle, rule name       │  │
│  └──────────────────────────┬───────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  VERSION SYNCHRONIZATION ENGINE                                  │  │
│  │  • WSP updated → flag corresponding Rego rules for review       │  │
│  │  • Rego rule updated → flag corresponding WSP section for review│  │
│  │  • All changes logged with who, when, why                       │  │
│  └──────────────────────────┬───────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  FINRA EXAMINATION REPORT GENERATOR                              │  │
│  │  Produces: "Here are our WSPs, here is the technical             │  │
│  │  implementation of each, and here is proof they are enforced"    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 WSP Document Structure

The WSP is organized into sections that map to OPA policy bundles:

| WSP Section | Title | OPA Policy Bundle | Description |
|-------------|-------|-------------------|-------------|
| 1.0 | AI Agent Supervisory Overview | `authority/` | General supervisory framework for AI agent operations |
| 2.0 | Agent Identity and Authorization | `authority/identity.rego` | How agent identities are issued, verified, and revoked |
| 3.0 | Data Access and MNPI Handling | `mnpi/` | Per-archetype data filtering, Chinese wall enforcement |
| 4.0 | Restricted List Management | `authority/restricted_list.rego` | How restricted securities are managed and enforced |
| 5.0 | Trade Execution Oversight | `authority/execution.rego` | HITL gates, order approval workflow, pre-trade compliance |
| 6.0 | Communication Review | `authority/communication.rego` | FINRA 2210 compliance, principal review of agent outputs |
| 7.0 | Record Retention | `authority/retention.rego` | WORM storage, 6-year retention, third-party access |
| 8.0 | Ongoing Monitoring and Surveillance | `authority/monitoring.rego` | BSA/AML hooks, exception monitoring, alert escalation |
| 9.0 | Account-Type Specific Procedures | `authority/account_type.rego` | ERISA, IRA, trust-specific rules (GAP 5) |
| 10.0 | Cross-Border Operations | `authority/jurisdiction.rego` | Jurisdiction-specific rules (GAP 7) |

### 3.4 Cross-Reference Mapping Format

```yaml
# wsp-to-rego-mapping.yaml — the cross-reference document
version: "1.0.0"
last_updated: "2026-07-15"
last_updated_by: "compliance_sme@acmewm.com"

mappings:
  - wsp_section: "4.2"
    wsp_title: "Restricted List Management"
    wsp_text: |
      The firm maintains a restricted list of securities that may not be
      recommended or traded by any registered representative or AI agent.
      The restricted list is updated by the Chief Compliance Officer and
      takes effect within 60 seconds of publication. Any recommendation
      or order involving a restricted security must be blocked and the
      attempt logged to the compliance audit trail.
    opa_bundle: "authority"
    rego_file: "authority/restricted_list.rego"
    rego_rule: "check_restricted_list"
    enforcement_type: "deterministic"
    test_cases:
      - "ADV-001: Query about restricted security → DENIED"
      - "ADV-RESTRICTED-001: Order for restricted security → BLOCKED"
    evidence_query: |
      SELECT * FROM audit_log
      WHERE rule_applied = 'authority/restricted_list.rego'
      AND decision = 'DENY'
      ORDER BY timestamp DESC
    last_wsp_review: "2026-07-01"
    last_rego_review: "2026-07-01"
    reviewer: "compliance_sme@acmewm.com"

  - wsp_section: "5.1"
    wsp_title: "Mandatory Human Approval for Trade Execution"
    wsp_text: |
      No AI agent may submit a trade order to any custodian or exchange
      without prior written approval from the supervising registered
      representative. Approval must be recorded with the approver's
      identity, timestamp, and a tamper-proof hash of the order details.
      Orders not approved within 24 hours are automatically cancelled.
    opa_bundle: "authority"
    rego_file: "authority/execution.rego"
    rego_rule: "require_hitl_approval"
    enforcement_type: "deterministic"
    test_cases:
      - "ADV-007: Buy order without approval → REQUIRE_APPROVAL"
      - "ADV-EXEC-001: Order auto-cancel after 24hr timeout"
    evidence_query: |
      SELECT * FROM hitl_gates
      WHERE specialist = 'execution'
      AND status IN ('APPROVED', 'TIMED_OUT', 'REJECTED')
      ORDER BY timestamp DESC
    last_wsp_review: "2026-07-01"
    last_rego_review: "2026-07-01"
    reviewer: "compliance_sme@acmewm.com"
```

### 3.5 Sample WSP Section with Corresponding Rego Rule

**WSP Section 4.2 — Restricted List Management:**

> The firm maintains a restricted list of securities that may not be recommended or traded by any registered representative or AI agent. The restricted list is updated by the Chief Compliance Officer and takes effect within 60 seconds of publication. Any recommendation or order involving a restricted security must be blocked and the attempt logged to the compliance audit trail.

**Corresponding Rego Rule:**

```rego
# authority/restricted_list.rego
package authority.restricted_list

import rego.v1

# Restricted list loaded from OPA bundle data
# Updated via bundle sync — propagation SLA: <60 seconds

default check_restricted_list := {
    "decision": "DENY",
    "reason": "restricted list check failed — default deny"
}

check_restricted_list := result if {
    not is_restricted(input.security_id)
    result := {
        "decision": "ALLOW",
        "reason": sprintf("Security %s is not on the restricted list", [input.security_id]),
        "rule": "authority/restricted_list.rego:check_restricted_list",
        "wsp_section": "4.2"
    }
}

check_restricted_list := result if {
    is_restricted(input.security_id)
    result := {
        "decision": "DENY",
        "reason": sprintf("Security %s is on the restricted list — blocked per WSP 4.2", [input.security_id]),
        "rule": "authority/restricted_list.rego:check_restricted_list",
        "wsp_section": "4.2",
        "restricted_since": data.restricted_list[input.security_id].added_date,
        "restricted_by": data.restricted_list[input.security_id].added_by
    }
}

is_restricted(security_id) if {
    data.restricted_list[security_id]
    data.restricted_list[security_id].status == "active"
}
```

**Restricted List Data (OPA bundle data):**

```json
{
  "restricted_list": {
    "ACME": {
      "status": "active",
      "added_date": "2026-07-10",
      "added_by": "cco@acmewm.com",
      "reason": "Pending M&A announcement",
      "expires": null
    },
    "XYZ": {
      "status": "active",
      "added_date": "2026-06-15",
      "added_by": "cco@acmewm.com",
      "reason": "Material non-public information",
      "expires": "2026-08-15"
    }
  }
}
```

### 3.6 Version Synchronization

```
WSP UPDATED:
  1. Compliance SME edits WSP Section 4.2 in Git
  2. CI/CD detects WSP change
  3. Cross-reference registry identifies linked Rego rules:
     → authority/restricted_list.rego:check_restricted_list
  4. System creates a review ticket:
     "WSP 4.2 updated — verify Rego rule still matches"
  5. Until Rego review is completed, mapping status = "PENDING_REVIEW"
  6. Review completion logged to audit trail

REGO RULE UPDATED:
  1. Engineer updates authority/restricted_list.rego in Git
  2. CI/CD detects Rego change
  3. Cross-reference registry identifies linked WSP sections:
     → WSP Section 4.2
  4. System creates a review ticket:
     "Rego rule updated — verify WSP 4.2 still accurate"
  5. Until WSP review is completed, mapping status = "PENDING_REVIEW"
  6. Review completion logged to audit trail

AUDIT TRAIL FOR EVERY CHANGE:
  {
    "change_id": "chg-uuid",
    "timestamp": "2026-07-15T10:00:00Z",
    "changed_by": "compliance_sme@acmewm.com",
    "change_type": "wsp_update",
    "wsp_section": "4.2",
    "linked_rego_rules": ["authority/restricted_list.rego:check_restricted_list"],
    "reason": "Updated propagation SLA from 120s to 60s per CCO directive",
    "review_status": "PENDING_REVIEW",
    "git_commit": "abc123"
  }
```

### 3.7 FINRA Examination Report Generator

Produces the document a FINRA examiner would ask for:

```
FINRA EXAMINATION REPORT
Generated: 2026-07-15
Firm: Acme Wealth Management (CRD# 12345)

SECTION 1: AI AGENT SUPERVISORY PROCEDURES SUMMARY
  Total WSP Sections: 10
  Total OPA Rules: 87
  Total Mappings: 142
  Mappings in Sync: 138 (97.2%)
  Mappings Pending Review: 4 (2.8%)

SECTION 2: PER-WSP-SECTION DETAIL
  WSP 4.2: Restricted List Management
    Status: IN SYNC
    OPA Rule: authority/restricted_list.rego:check_restricted_list
    Enforcement: Deterministic (fail-closed)
    Propagation SLA: <60 seconds
    Last WSP Review: 2026-07-01 by compliance_sme@acmewm.com
    Last Rego Review: 2026-07-01 by compliance_sme@acmewm.com
    Test Cases: 2 passing (ADV-001, ADV-RESTRICTED-001)
    Enforcement Evidence (last 30 days):
      - 12 restricted list checks performed
      - 2 DENY decisions (securities ACME, XYZ)
      - 10 ALLOW decisions
      - 0 bypasses

SECTION 3: ENFORCEMENT PROOF
  For each WSP section:
    - Rule evaluation count (last 30/90/365 days)
    - DENY/ALLOW/WARN breakdown
    - Zero bypass attestation
    - Adversarial test results (last run date, pass/fail)

SECTION 4: CHANGE HISTORY
  All WSP and Rego changes in the reporting period
  with who, when, why, and review status
```

### 3.8 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~500 Python (sync engine + report generator) + ~300 YAML (mapping schema + sample mappings) + ~200 Rego (wsp_section annotations in existing rules) |
| **Modules Affected** | M2/M4 (OPA rules: add wsp_section annotations), M5 (config: WSP mapping file path), M10 (audit: change tracking) |
| **SME Deliverables** | All WSP section text (human-readable supervisory procedures), mapping of each WSP section to technical controls, review sign-off on each mapping |
| **Buildable Without SME** | Cross-reference registry schema, version sync engine, CI/CD hooks for change detection, FINRA report generator template, audit trail for changes |
| **Implementation Phase** | Phase 2 (Weeks 12–28) — WSP document must exist before FINRA engagement (Phase 0 item 0.7) but full mapping system in Phase 2 |


---
---

## GAP 4: BSA/AML ONGOING MONITORING

### 4.1 Regulatory Context

The Bank Secrecy Act (BSA) and Anti-Money Laundering (AML) regulations require financial institutions to file Suspicious Activity Reports (SARs), Currency Transaction Reports (CTRs) for cash transactions exceeding $10,000, and maintain ongoing Customer Due Diligence (CDD) programs. The v2 Onboarding Specialist handles KYC/sanctions at account opening, but ongoing BSA/AML monitoring is absent.

### 4.2 Module Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BSA/AML MONITORING MODULE                            │
│                    (Integrated with M2/M4 OPA + M10 Audit)             │
│                                                                         │
│  REAL-TIME TRANSACTION MONITORING                                      │
│  Every wire/trade passes through before HITL gate                      │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ CTR Threshold │  │ SAR Pattern  │  │ Sanctions    │                 │
│  │ Check (>$10K) │  │ Detection    │  │ Screen       │                 │
│  │ Deterministic │  │ (structuring,│  │ (OFAC, EU,   │                 │
│  │              │  │  velocity,   │  │  UN lists)   │                 │
│  │              │  │  geography)  │  │ Deterministic │                 │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
│         └─────────────────┼─────────────────┘                          │
│                           ▼                                             │
│  ┌──────────────────────────────────────────────────────┐              │
│  │  ALERT ROUTER                                        │              │
│  │  CTR → automated filing data prep                    │              │
│  │  SAR trigger → compliance officer (NOT advisor)      │              │
│  │  Sanctions hit → BLOCK transaction + escalate        │              │
│  └──────────────────────────────────────────────────────┘              │
│                                                                         │
│  BATCH CDD MONITORING (periodic — daily/weekly)                        │
│  • Risk profile change detection                                       │
│  • Adverse media screening                                             │
│  • Sanctions list update re-screening                                  │
│  • Unusual activity pattern analysis                                   │
│  • CDD refresh triggers (high=12mo, med=24mo, low=36mo)              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 OPA Rules for SAR Trigger Detection

```rego
# authority/bsa_aml/sar_triggers.rego
package authority.bsa_aml.sar_triggers

import rego.v1

# SAR Trigger 1: Structuring — multiple cash transactions just below $10K
structuring_alert := result if {
    transactions := data.client_transactions[input.client_id]
    window_txns := [t | t := transactions[_]; within_window(t.timestamp, 5)]
    cash_txns := [t | t := window_txns[_]; t.type == "cash"; t.amount >= 8000; t.amount < 10000]
    count(cash_txns) >= 3
    total := sum([t.amount | t := cash_txns[_]])
    total >= 25000
    result := {
        "alert_type": "SAR_STRUCTURING",
        "severity": "HIGH",
        "client_id": input.client_id,
        "description": sprintf("Potential structuring: %d cash txns totaling $%d in 5-day window", [count(cash_txns), total]),
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "8.1"
    }
}

# SAR Trigger 2: Rapid movement of funds
rapid_movement_alert := result if {
    transactions := data.client_transactions[input.client_id]
    window_txns := [t | t := transactions[_]; within_window(t.timestamp, 3)]
    wire_in := sum([t.amount | t := window_txns[_]; t.type == "wire_in"])
    wire_out := sum([t.amount | t := window_txns[_]; t.type == "wire_out"])
    wire_in > 50000
    wire_out > wire_in * 0.8
    result := {
        "alert_type": "SAR_RAPID_MOVEMENT",
        "severity": "HIGH",
        "client_id": input.client_id,
        "description": sprintf("Rapid fund movement: $%d in, $%d out within 3 days", [wire_in, wire_out]),
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "8.1"
    }
}

# SAR Trigger 3: Geographic risk — wire to high-risk jurisdiction
geographic_risk_alert := result if {
    input.wire_destination_country != null
    data.high_risk_jurisdictions[input.wire_destination_country]
    input.amount > 5000
    result := {
        "alert_type": "SAR_GEOGRAPHIC_RISK",
        "severity": "MEDIUM",
        "client_id": input.client_id,
        "description": sprintf("Wire of $%d to high-risk jurisdiction: %s", [input.amount, input.wire_destination_country]),
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "8.1"
    }
}

# SAR Trigger 4: Unusual wire volume vs. historical average
unusual_wire_alert := result if {
    client_profile := data.client_profiles[input.client_id]
    transactions := data.client_transactions[input.client_id]
    avg_monthly := client_profile.avg_monthly_wire_volume
    current_month := sum([t.amount | t := transactions[_]; within_window(t.timestamp, 30); t.type in {"wire_in", "wire_out"}])
    current_month > avg_monthly * 3
    result := {
        "alert_type": "SAR_UNUSUAL_PATTERN",
        "severity": "MEDIUM",
        "client_id": input.client_id,
        "description": sprintf("Wire volume $%d exceeds 3x monthly avg of $%d", [current_month, avg_monthly]),
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "8.1"
    }
}

within_window(ts, days) if {
    now := time.now_ns()
    ts_ns := time.parse_rfc3339_ns(ts)
    diff := now - ts_ns
    diff < days * 24 * 60 * 60 * 1000000000
}
```

### 4.4 CTR Threshold Monitoring

```rego
# authority/bsa_aml/ctr.rego
package authority.bsa_aml.ctr

import rego.v1

# CTR required for cash transactions > $10,000 (single or aggregate per day)
ctr_required := result if {
    input.transaction_type == "cash"
    input.amount > 10000
    result := {
        "ctr_required": true,
        "amount": input.amount,
        "client_id": input.client_id,
        "action": "generate_ctr_filing_data",
        "wsp_section": "8.2"
    }
}

aggregate_ctr_required := result if {
    transactions := data.client_transactions[input.client_id]
    today_cash := [t | t := transactions[_]; same_business_day(t.timestamp); t.type == "cash"]
    total := sum([t.amount | t := today_cash[_]])
    total > 10000
    result := {
        "ctr_required": true,
        "aggregate_amount": total,
        "transaction_count": count(today_cash),
        "client_id": input.client_id,
        "action": "generate_ctr_filing_data",
        "wsp_section": "8.2"
    }
}
```

### 4.5 Integration with Existing Modules

**Onboarding Specialist (Line 5) → BSA/AML Module:**
- Account opening KYC feeds initial CDD record (client_id, risk_rating, KYC data hash, sanctions screen result)
- BSA/AML module takes over ongoing monitoring from that point

**Execution Specialist (Line 4) → BSA/AML Module:**
- Every wire/trade passes through BSA/AML checks pre-HITL gate (alongside existing restricted list, concentration, suitability checks)
- New checks: CTR threshold, SAR pattern detection, sanctions re-screen, geographic risk

### 4.6 Anti-Tipping-Off Escalation

**Critical: When a SAR trigger fires, the advisor must NOT be notified. Tipping off is a federal crime under 31 U.S.C. § 5318(g)(2).**

- SAR alerts route to compliance officer via dedicated compliance channel (NOT shared Slack)
- Advisor sees only generic message: "Transaction requires additional compliance review"
- SAR alert logging goes to compliance-only partition in M10 (not visible in advisor-facing CRM)
- Compliance officer can: dismiss (false positive — logged), investigate, or file SAR

**SAR Narrative Assistance:** When compliance officer decides to file, LLM (Haiku) generates a draft narrative from structured alert data. Compliance officer MUST review and approve before filing. SAR narrative stored in compliance-only partition.

### 4.7 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~600 Rego (SAR triggers + CTR + sanctions) + ~400 Python (batch CDD + SAR narrative + alert router) + ~100 YAML config |
| **Modules Affected** | M2/M4 (OPA: new `bsa_aml/` policy bundle), M10 (compliance-only audit partition), M12 Execution Specialist (pre-HITL checks), M12 Onboarding Specialist (KYC → CDD handoff) |
| **SME Deliverables** | SAR trigger thresholds, high-risk jurisdiction list, CDD refresh frequency per risk tier, CTR filing format, SAR narrative template, escalation procedures |
| **Buildable Without SME** | OPA rule framework, alert routing, anti-tipping-off enforcement, batch CDD scheduler, SAR narrative LLM template, WORM logging |
| **Implementation Phase** | Phase 3 (Weeks 24–36) — after Execution Specialist operational. Basic sanctions screening in Phase 2 via Onboarding. |


---
---

## GAP 5: ERISA ACCOUNT-TYPE AWARENESS

### 5.1 Regulatory Context

Different account types are governed by different regulatory regimes. A recommendation suitable for a taxable account may violate ERISA for a retirement account.

| Account Type | Regulatory Regime | Key Constraints |
|-------------|-------------------|-----------------|
| **Taxable** | Reg BI (BD) / Fiduciary (RIA) | Standard suitability; capital gains tax implications |
| **Traditional IRA** | Fiduciary + IRC prohibited transaction rules | No self-dealing; no party-in-interest transactions; RMD requirements |
| **Roth IRA** | Fiduciary + IRC rules | Contribution limits; 5-year rule; no RMDs during owner's lifetime |
| **401(k)** | ERISA + DOL fiduciary rule | Prohibited transactions; prudent investor rule; plan document constraints; limited investment menu |
| **Trust** | State trust law + Prudent Investor Rule | Duty of loyalty; duty of impartiality (income vs. remainder beneficiaries) |
| **Custodial (UTMA/UGMA)** | State UTMA/UGMA statutes | Minor's account; prudent investor standard; restricted investment types |
| **ERISA pension** | ERISA §404 + DOL regulations | Strictest fiduciary standard; prohibited transaction exemptions (PTEs) |

### 5.2 Canonical Schema Extension

Add `account_type` to Client, Holding, and Order canonical types in M3:

```json
{
  "title": "Client.accounts[] — account_type extension",
  "properties": {
    "account_id": { "type": "string" },
    "account_type": {
      "type": "string",
      "enum": [
        "taxable", "traditional_ira", "roth_ira", "401k", "403b", "457",
        "sep_ira", "simple_ira", "trust_revocable", "trust_irrevocable",
        "custodial_utma", "custodial_ugma", "erisa_pension",
        "erisa_profit_sharing", "529", "hsa"
      ]
    },
    "tax_status": {
      "type": "string",
      "enum": ["taxable", "tax_deferred", "tax_exempt", "tax_advantaged"]
    },
    "erisa_governed": { "type": "boolean" },
    "plan_document_constraints": {
      "type": ["object", "null"],
      "description": "For 401k/pension: investment menu restrictions from plan document"
    },
    "trust_terms": {
      "type": ["object", "null"],
      "description": "For trusts: income vs. remainder beneficiary split, distribution rules"
    },
    "rmd_due_date": {
      "type": ["string", "null"], "format": "date",
      "description": "Required Minimum Distribution due date (IRA/401k for age 73+)"
    }
  }
}
```

**Order type extension** adds `account_type`, `erisa_governed`, and `tax_impact` (estimated capital gains, holding period, wash sale risk) to every order for compliance check context.

### 5.3 OPA Policy Bundles Per Account Type

Account-type rules layer ON TOP of existing archetype rules:

```rego
# authority/account_type/erisa.rego
package authority.account_type.erisa

import rego.v1

# ERISA §406: Prohibited transaction — plan vs. party-in-interest
check_prohibited_transaction := result if {
    input.account_type in {"401k", "403b", "erisa_pension", "erisa_profit_sharing"}
    is_party_in_interest(input.counterparty_id)
    result := {
        "decision": "DENY",
        "reason": sprintf("Prohibited transaction: %s is a party-in-interest under ERISA §406", [input.counterparty_id]),
        "rule": "authority/account_type/erisa.rego:check_prohibited_transaction",
        "wsp_section": "9.1",
        "account_type": input.account_type
    }
}

# Stricter concentration for ERISA (10% vs standard 15%)
check_erisa_concentration := result if {
    input.account_type in {"401k", "403b", "erisa_pension", "erisa_profit_sharing"}
    input.proposed_position_pct > 10
    result := {
        "decision": "WARN",
        "reason": sprintf("ERISA prudent investor: %d%% concentration exceeds 10%% guideline", [input.proposed_position_pct]),
        "rule": "authority/account_type/erisa.rego:check_erisa_concentration",
        "wsp_section": "9.1"
    }
}

# 401k plan investment menu check
check_plan_investment_menu := result if {
    input.account_type in {"401k", "403b"}
    plan_menu := data.plan_investment_menus[input.plan_id]
    not plan_menu[input.security_id]
    result := {
        "decision": "DENY",
        "reason": sprintf("Security %s not in plan's approved investment menu", [input.security_id]),
        "rule": "authority/account_type/erisa.rego:check_plan_investment_menu",
        "wsp_section": "9.1"
    }
}

is_party_in_interest(entity_id) if {
    data.party_in_interest_list[entity_id]
}
```

```rego
# authority/account_type/ira.rego
package authority.account_type.ira

import rego.v1

# RMD check — flag if client 73+ and RMD not yet taken
check_rmd_status := result if {
    input.account_type in {"traditional_ira", "401k", "403b", "sep_ira", "simple_ira"}
    input.client_age >= 73
    input.rmd_taken_this_year == false
    input.current_month >= 10
    result := {
        "decision": "WARN",
        "reason": sprintf("RMD not yet taken for %s — due by December 31", [input.account_type]),
        "rule": "authority/account_type/ira.rego:check_rmd_status",
        "wsp_section": "9.2",
        "flag_in_meeting_prep": true
    }
}

# Roth IRA 5-year rule
check_roth_5year := result if {
    input.account_type == "roth_ira"
    input.action == "withdraw"
    input.roth_account_age_years < 5
    input.client_age < 59.5
    result := {
        "decision": "WARN",
        "reason": "Roth withdrawal may incur penalties — account < 5 years and client under 59.5",
        "rule": "authority/account_type/ira.rego:check_roth_5year",
        "wsp_section": "9.2"
    }
}
```

```rego
# authority/account_type/trust.rego
package authority.account_type.trust

import rego.v1

# Trust duty of impartiality — balance income vs. growth
check_trust_impartiality := result if {
    input.account_type in {"trust_revocable", "trust_irrevocable"}
    input.trust_has_income_beneficiary == true
    input.trust_has_remainder_beneficiary == true
    input.portfolio_income_yield < 0.02
    input.security_yield == 0
    result := {
        "decision": "WARN",
        "reason": "Trust impartiality concern: portfolio yield < 2% and buying non-income security. Consider income beneficiary needs.",
        "rule": "authority/account_type/trust.rego:check_trust_impartiality",
        "wsp_section": "9.3"
    }
}
```

### 5.4 Integration with Specialists

**Client Service Specialist (meeting prep):** Injects account-type flags — e.g., "Henderson's IRA has RMD due this year", "Trust distribution due per trust terms".

**Execution Specialist (pre-HITL gate):** Runs account-type checks alongside existing compliance checks. Adds tax impact calculation:

```
Tax Impact Comparison (shown to advisor at HITL gate):
  "Selling NVDA in taxable account triggers $12K long-term capital gains
   Selling NVDA in IRA has no tax impact (tax-deferred)
   Consider tax-loss harvesting in taxable; sell in IRA instead"
```

Tax impact is calculated deterministically (not LLM) from cost basis, holding period, and client tax bracket.

### 5.5 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~500 Rego (ERISA + IRA + trust + custodial rules) + ~300 Python (tax calculator + account-type flags) + ~150 JSON Schema |
| **Modules Affected** | M2/M4 (OPA: `account_type/` bundle), M3 (schema extensions), M12 Client Service (meeting prep flags), M12 Execution (pre-HITL checks + tax impact) |
| **SME Deliverables** | ERISA prohibited transaction rules, party-in-interest list, plan document constraints per 401k, trust rules per state, concentration limits per account type |
| **Buildable Without SME** | OPA rule framework, schema extensions, tax calculator, account-type flag system, specialist integration |
| **Implementation Phase** | Phase 2 (schema extensions — Weeks 12–16) + Phase 3 (full ERISA/trust rules — Weeks 24–36) |


---
---

## GAP 6: MNPI LEAKAGE SCAN

### 6.1 Problem Statement

M4 strips sensitive fields from LLM input. But what if the LLM infers or reconstructs MNPI from the data it DID receive? This output guardrail (position [5] in the v2 guardrail composition) detects such leakage before output reaches the user.

### 6.2 Three-Layer Detection Architecture

```
LLM OUTPUT
     │
     ▼
LAYER A: KEYWORD / PATTERN MATCHING                          <10ms
  Compare output against MNPI filter log values.
  If M4 stripped "1,200 shares" and output contains "1,200" → FLAG
  If M4 stripped "$2.4M" and output contains "$2.4M" → FLAG
  Implementation: Deterministic regex/string matching
  False positive rate: ~30%
     │ if flagged
     ▼
LAYER B: ENTITY EXTRACTION + COMPARISON                      <100ms
  Extract financial entities (tickers, amounts, percentages) via NER.
  Compare against MNPI filter log:
  • Entity in output AND in filtered data → FLAG
  • Entity in output AND NOT in provided data → FLAG (inferred)
  • Entity in output AND in provided data → PASS (legitimate)
  Implementation: spaCy NER + custom financial entity extractor
  False positive rate: ~15%
     │ if flagged
     ▼
LAYER C: SECONDARY LLM CLASSIFIER                           <2s
  Haiku call: "Does this output contain MNPI about {client/fund}
  that should not be disclosed to {role}?"
  Structured output: {contains_mnpi, confidence, flagged_phrases, explanation}
  Implementation: Haiku function calling
  False positive rate: ~10%
     │
     ▼
DECISION ENGINE:
  Layer A only → DELIVER + review queue
  Layer A + B → DELIVER + review queue (priority HIGH)
  Layer A + B + C (confidence > 0.8) → BLOCK, regenerate (max 2 retries)
  Layer C alone (confidence > 0.9) → BLOCK + escalate
  All flags logged to M10 WORM regardless of decision
```

### 6.3 MNPI Filter Log Schema

M4 produces a filter log for every request, recording what was stripped:

```json
{
  "filter_log_id": "flog-uuid",
  "trace_id": "trace-abc-123",
  "archetype": "tier1_investment_bank",
  "role": "public_side_analyst",
  "fields_stripped": [
    {
      "field_path": "holdings[0].quantity",
      "original_value": "1200",
      "value_type": "integer",
      "mnpi_category": "position_size"
    },
    {
      "field_path": "holdings[0].market_value",
      "original_value": "2400000",
      "value_type": "currency",
      "mnpi_category": "position_value"
    }
  ],
  "fields_retained": ["holdings[*].ticker", "holdings[*].sector"],
  "policy_bundle": "mnpi/v1.4.2",
  "rule_applied": "mnpi/tier1_public_side.rego"
}
```

### 6.4 Layer A Implementation

```python
# mnpi_leakage_scan/layer_a.py
import re

class LayerAScanner:
    """Keyword/pattern matching against MNPI filter log. Target: <10ms."""
    
    def scan(self, output: str, filter_log: MNPIFilterLog) -> list[LeakageFlag]:
        flags = []
        for stripped in filter_log.fields_stripped:
            patterns = self._value_patterns(stripped.original_value, stripped.value_type)
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    flags.append(LeakageFlag(
                        layer="A", field_path=stripped.field_path,
                        matched_pattern=pattern, original_value=stripped.original_value,
                        mnpi_category=stripped.mnpi_category, confidence=0.6,
                    ))
        return flags
    
    def _value_patterns(self, value: str, vtype: str) -> list[str]:
        patterns = [re.escape(value)]
        if vtype == "integer":
            n = int(value)
            patterns += [f"{n:,}", str(n)]
            if n >= 1000: patterns.append(f"{n/1000:.1f}K")
        elif vtype == "currency":
            n = int(value)
            patterns += [f"\\${n:,}", f"\\${n}"]
            if n >= 1_000_000: patterns += [f"\\${n/1_000_000:.1f}M", f"\\${n/1_000_000:.1f} million"]
            elif n >= 1_000: patterns.append(f"\\${n/1_000:.0f}K")
        return patterns
```

### 6.5 Layer B Implementation

```python
# mnpi_leakage_scan/layer_b.py
import spacy

class LayerBScanner:
    """Entity extraction + comparison. Target: <100ms."""
    
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.fin_patterns = FinancialEntityPatterns()  # Custom ticker/amount/pct extractors
    
    def scan(self, output: str, filter_log: MNPIFilterLog, provided_data: dict) -> list[LeakageFlag]:
        entities = self.fin_patterns.extract(self.nlp(output))
        flags = []
        for entity in entities:
            if self._in_filter_log(entity, filter_log):
                flags.append(LeakageFlag(layer="B", entity_type=entity.type,
                    entity_value=entity.value, match_type="filtered_data_match", confidence=0.75))
            elif not self._in_provided_data(entity, provided_data):
                flags.append(LeakageFlag(layer="B", entity_type=entity.type,
                    entity_value=entity.value, match_type="inferred_data", confidence=0.7))
        return flags
```

### 6.6 Layer C Prompt

```python
LAYER_C_PROMPT = """You are a compliance reviewer for a financial services AI agent.

The following output was generated for a user with:
- Role: {role}
- Archetype: {archetype}

The following data fields were FILTERED (stripped) from the LLM's input by the MNPI policy engine:
{filtered_fields_summary}

The following data was PROVIDED to the LLM:
{provided_fields_summary}

LLM Output to review:
{llm_output}

Does this output contain material non-public information about {subject} that should not be disclosed to a {role}?

Respond with JSON:
{{"contains_mnpi": true/false, "confidence": 0.0-1.0, "flagged_phrases": [...], "explanation": "..."}}"""
```

### 6.7 False Positive Handling

- Flagged outputs go to a compliance officer review queue (4-hour SLA)
- If confirmed leak: output retroactively blocked, incident logged to WORM, M4 rules reviewed for gap
- If false positive: dismissed with reason, pattern added to allowlist, logged for accuracy tracking
- Accuracy metrics tracked over time: recall, precision, false positive rate per layer

### 6.8 Performance and Accuracy Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Total overhead (typical)** | <10ms | 85% of outputs pass Layer A with no flag |
| **Total overhead (worst case)** | <2.5s | Only ~5% of outputs reach Layer C |
| **Recall** | >95% | Must catch 95%+ of actual leaks |
| **Precision** | >80% | Accept 20% false positive rate — over-flag preferred for MNPI |

### 6.9 Integration

Sits at guardrail position [6] (renumbered from v2 [5]) in the output guardrail stack. Consumes the MNPI filter log produced by M4 at guardrail position [5]. All scan results (pass, flag, block) logged to M10 WORM.

### 6.10 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~400 Python (Layer A + B + C + decision engine) + ~100 Python (review queue API) + ~50 JSON Schema |
| **Modules Affected** | M4 (produces filter log), M6 (scanner in output path), M10 (flag logging to WORM), M12 (all specialist outputs pass through) |
| **SME Deliverables** | MNPI field patterns per archetype, inferred-vs-legitimate threshold, escalation procedure, review queue SLA |
| **Buildable Without SME** | Layer A regex scanner, Layer B NER, Layer C prompt, decision engine, review queue, WORM logging, accuracy tracking |
| **Implementation Phase** | Phase 1 (Layer A — Weeks 8–12) + Phase 2 (Layers B+C — Weeks 14–20, tuning with real data) |


---
---

## GAP 7: CROSS-BORDER REGULATORY ARCHITECTURE

### 7.1 Problem Statement

The v2 architecture is US-centric. For firms with international operations, the platform must enforce different regulatory regimes in different jurisdictions. The committee found no architectural design for jurisdiction-aware OPA policies, conflict resolution, or data residency enforcement.

### 7.2 Jurisdiction Field in Enterprise Config

```yaml
# enterprise-config.yaml — jurisdiction section
jurisdiction:
  primary: "US"
  additional: ["EU", "UK"]
  data_residency: "US"
  
  us:
    regulator: "FINRA/SEC"
    suitability_standard: "reg_bi"       # reg_bi | fiduciary
    retention_years: 6
    worm_required: true
    
  eu:
    regulator: "ESMA/NCA"
    suitability_standard: "mifid2"
    retention_years: 5
    gdpr_enabled: true
    dora_enabled: true
    ai_act_enabled: true
    data_residency: "EU"
    consent_required_for_llm: true
    dpia_required: true
    
  uk:
    regulator: "FCA"
    suitability_standard: "consumer_duty"
    retention_years: 5
    gdpr_uk_enabled: true
    consumer_duty_outcomes:
      - "products_and_services"
      - "price_and_value"
      - "consumer_understanding"
      - "consumer_support"
    
  sg:
    regulator: "MAS"
    trm_enabled: true
    feat_enabled: true
    airg_enabled: true
    
  hk:
    regulator: "SFC"
    meaningful_human_oversight: true
```

**Propagation:** Loaded by M5, propagated to all modules via request context. Every OPA evaluation includes `input.jurisdiction` so rules branch per jurisdiction.

### 7.3 OPA Policy Bundle Structure Per Jurisdiction

```
opa-bundles/
├── authority/                    # Base rules (all jurisdictions)
├── mnpi/                        # Base MNPI rules
├── account_type/                # GAP 5 rules
├── bsa_aml/                     # GAP 4 rules
│
├── jurisdiction/                # Jurisdiction-specific overlays
│   ├── us/
│   │   ├── reg_bi.rego         # Reg BI suitability
│   │   ├── finra_2210.rego     # Communication review
│   │   └── rule_17a4.rego      # Record retention
│   │
│   ├── eu/
│   │   ├── mifid2_suitability.rego    # MiFID II suitability
│   │   ├── mifid2_best_execution.rego # Best execution reporting
│   │   ├── mifid2_research.rego       # Research unbundling
│   │   ├── mifid2_transaction.rego    # T+1 transaction reporting
│   │   ├── gdpr_consent.rego          # Consent management
│   │   ├── gdpr_erasure.rego          # Right-to-erasure + legal hold
│   │   ├── dora_ict.rego              # ICT third-party register
│   │   ├── dora_incident.rego         # 4-hour incident reporting
│   │   └── ai_act.rego               # EU AI Act high-risk
│   │
│   ├── uk/
│   │   ├── fca_consumer_duty.rego     # Consumer Duty outcomes
│   │   └── uk_gdpr.rego              # UK GDPR
│   │
│   ├── sg/
│   │   ├── mas_trm.rego              # Technology Risk Management (1hr incident reporting)
│   │   ├── mas_feat.rego             # FEAT principles (Fairness, Ethics, Accountability, Transparency)
│   │   └── mas_airg.rego             # AI Risk Management Guidelines (inventory, materiality, controls)
│   │
│   └── hk/
│       └── sfc_ai.rego               # SFC AI oversight
│
└── data/                        # Jurisdiction-specific data
    ├── us/restricted_list.json
    ├── eu/sanctions_list.json
    └── uk/fca_restricted_list.json
```

OPA loads base bundles + jurisdiction overlay based on `enterprise_config.jurisdiction.primary`. Multi-jurisdiction firms load multiple overlays; conflict resolution (§7.4) determines precedence.

### 7.4 Conflict Resolution Hierarchy

```
PRIORITY (highest to lowest):

  1. SAFETY — Always wins. Any jurisdiction blocks → blocked.
  2. RETENTION — 17a-4 retention > GDPR erasure for regulated records.
  3. PRIVACY — GDPR data minimization applies; collect minimum for compliance.
  4. OPERATIONAL — Generate ALL required reports (more reporting > less).
```

**Key Conflict Resolutions:**

```rego
# jurisdiction/conflict_resolution.rego
package jurisdiction.conflict_resolution

import rego.v1

# GDPR erasure vs. 17a-4 retention
resolve_erasure_vs_retention := result if {
    input.request_type == "gdpr_erasure"
    input.data_category == "regulated_record"
    result := {
        "decision": "DENY_ERASURE",
        "reason": "Record subject to regulatory retention (17a-4/MiFID II)",
        "legal_basis": "GDPR Article 17(3)(b) — legal obligation",
        "action": "Mark for erasure after retention period expires"
    }
}

resolve_erasure_vs_retention := result if {
    input.request_type == "gdpr_erasure"
    input.data_category != "regulated_record"
    result := {
        "decision": "ALLOW_ERASURE",
        "action": "Erase from all systems within 30 days"
    }
}

# Suitability standard per jurisdiction
resolve_suitability := result if {
    input.jurisdiction == "EU"
    result := {"standard": "mifid2", "requires_knowledge_assessment": true}
}
resolve_suitability := result if {
    input.jurisdiction == "US"
    input.registration_type == "bd_only"
    result := {"standard": "reg_bi", "requires_care_doc": true}
}
resolve_suitability := result if {
    input.jurisdiction == "UK"
    result := {"standard": "consumer_duty", "requires_outcome_assessment": true}
}
```

### 7.5 Data Residency Routing

```
PII-PROCESSING MODULES (must run in data subject's jurisdiction):
  M1 (Identity), M4 (MNPI Filter), M6 (Gateway), M10 (Audit), M11 (Adapters)
  → EU clients: run in eu-central-1 (Frankfurt)
  → US clients: run in us-east-1
  → UK clients: run in eu-west-2 (London)

NON-PII MODULES (can run anywhere):
  M3 (Schema), M8 (Pipeline), M9 (Intent Router)
  → Run in primary region for cost/latency optimization

ROUTING: Request arrives with AID containing jurisdiction → M6 routes to
correct regional deployment → PII never leaves jurisdiction boundary
```

### 7.6 GDPR Specifics

**Consent Management:** Per-client consent records tracking LLM processing consent, cross-border transfer consent (with SCC references), and withdrawal mechanisms.

**DPIA Template:** For MNPI Policy Engine (M4) as automated decision-making — covers necessity, data categories, risk assessment, and DPO approval.

**DPA Tracking:** Every MCP server vendor, LLM provider, and cloud service registered as a data processor with DPA status, SCC requirements, and sub-processor lists.

**Right-to-Erasure Workflow:**
- Regulated records (trades, Reg BI docs, audit trail) → DENY erasure per GDPR Art. 17(3)(b), mark for erasure after retention period
- Non-regulated PII → ERASE within 30 days
- Memory layers L2-L5 → Erase; L6 compliance memory → Retained (regulated)

### 7.7 DORA Specifics

**Third-Party ICT Register:** Every MCP server, LLM provider, and cloud service catalogued with criticality rating, exit strategy, exit timeline, and concentration risk assessment.

**Incident Reporting:** Major incidents (data breach, >2hr outage, >100 clients affected, >€100K impact) require initial notification to NCA within 4 hours, intermediate report within 72 hours, final report within 30 days.

**Resilience Testing:** Framework hooks for threat-led penetration testing (TLPT) for significant entities.

### 7.8 MiFID II Specifics

```rego
# jurisdiction/eu/mifid2_suitability.rego
package jurisdiction.eu.mifid2_suitability

import rego.v1

# MiFID II requires knowledge/experience assessment before recommendation
check_mifid2_suitability := result if {
    input.jurisdiction == "EU"
    not input.client.knowledge_experience_assessed
    result := {
        "decision": "DENY",
        "reason": "MiFID II requires knowledge/experience assessment before recommendation",
        "action": "Complete client questionnaire",
        "wsp_section": "10.1"
    }
}

# Best execution — record venue selection rationale
check_best_execution := result if {
    input.jurisdiction == "EU"
    input.action == "execute_order"
    result := {
        "decision": "ALLOW",
        "additional_requirements": [
            "Record execution venue selection rationale",
            "Compare price against reference benchmarks",
            "Generate quarterly best execution report (MiFID II Art. 27)"
        ]
    }
}

# Research unbundling — separate research costs from execution
check_research_unbundling := result if {
    input.jurisdiction == "EU"
    input.action == "access_research"
    result := {
        "decision": "ALLOW",
        "additional_requirements": [
            "Track research cost attribution",
            "Separate research payment from execution commission",
            "Annual research budget disclosure"
        ]
    }
}
```

### 7.9 Multi-Jurisdiction Enterprise Config Sample

```yaml
firm:
  name: "Global Wealth Partners"
  lei: "5493001KJTIIGC8Y1R12"

jurisdiction:
  primary: "US"
  additional: ["EU", "UK"]

deployment:
  us_region:
    cloud: "aws"
    region: "us-east-1"
    modules: ["M1","M2","M3","M4","M5","M6","M7","M8","M9","M10","M11","M12"]
  eu_region:
    cloud: "aws"
    region: "eu-central-1"
    modules: ["M1","M4","M6","M10","M11"]  # PII-processing only
    data_residency_enforced: true
  uk_region:
    cloud: "aws"
    region: "eu-west-2"
    modules: ["M1","M4","M6","M10","M11"]

opa_bundles:
  base: ["authority/", "mnpi/", "account_type/", "bsa_aml/"]
  us_overlay: ["jurisdiction/us/"]
  eu_overlay: ["jurisdiction/eu/"]
  uk_overlay: ["jurisdiction/uk/"]
```

### 7.10 Summary

| Dimension | Value |
|-----------|-------|
| **Estimated LOC** | ~800 Rego (US ~200, EU ~300, UK ~150, SG ~75, HK ~75) + ~500 Python (consent manager + DPIA + DPA tracker + DORA incident + residency router + erasure workflow) + ~300 YAML config |
| **Modules Affected** | M2/M4 (jurisdiction overlay bundles), M5 (jurisdiction config), M6 (data residency routing), M10 (jurisdiction-specific retention), M1 (jurisdiction in AID), ALL modules (jurisdiction in request context) |
| **SME Deliverables** | Per-jurisdiction regulatory mapping, GDPR consent templates, DPIA content, DPA templates, DORA ICT register, MiFID II questionnaire, FCA Consumer Duty outcomes, conflict resolution decisions (legal counsel) |
| **Buildable Without SME** | OPA bundle structure, jurisdiction routing, consent tracking infra, DPA register schema, DORA incident hooks, erasure workflow, data residency enforcement, conflict resolution framework |
| **Implementation Phase** | Phase 3 (jurisdiction field + GDPR basics — Weeks 30–36) + Phase 5 (full MiFID II + DORA + FCA — Weeks 52–78, requires EU regulatory SME) |

---
---

## CROSS-GAP DEPENDENCY MAP

```
GAP 1 (Reg BI) ◄──── GAP 5 (Account Type) — account_type feeds into Reg BI docs
GAP 1 (Reg BI) ◄──── GAP 7 (Cross-Border) — MiFID II replaces Reg BI for EU clients
GAP 2 (Liability) ◄── ALL GAPS — provenance chain captures all compliance decisions
GAP 3 (WSP-YAML) ◄── ALL GAPS — every OPA rule needs wsp_section annotation
GAP 4 (BSA/AML) ◄──── GAP 5 (Account Type) — account type affects SAR thresholds
GAP 6 (MNPI Scan) ◄── GAP 7 (Cross-Border) — MNPI definitions vary by jurisdiction
GAP 7 (Cross-Border) ──► ALL GAPS — jurisdiction overlay affects every compliance rule
```

## IMPLEMENTATION PRIORITY

| Priority | Gap | Phase | Rationale |
|----------|-----|-------|-----------|
| **P0** | GAP 2: Liability (provenance chain) | Phase 1 | Built into M6/M10 from day one |
| **P0** | GAP 6: MNPI Leakage Scan (Layer A) | Phase 1 | Core compliance guardrail |
| **P1** | GAP 1: Reg BI Documentation | Phase 2 | Required before BD lighthouse |
| **P1** | GAP 3: WSP-to-YAML Mapping | Phase 2 | Required before FINRA engagement |
| **P1** | GAP 5: Account-Type (schema) | Phase 2 | Schema extensions needed early |
| **P2** | GAP 4: BSA/AML Monitoring | Phase 3 | After Execution Specialist |
| **P2** | GAP 5: Account-Type (ERISA rules) | Phase 3 | Full rules need SME |
| **P2** | GAP 6: MNPI Leakage (Layers B+C) | Phase 2 | Tuning needs real data |
| **P3** | GAP 7: Cross-Border (GDPR basics) | Phase 3 | Jurisdiction field + consent |
| **P3** | GAP 7: Cross-Border (full MiFID/DORA) | Phase 5 | Requires EU regulatory SME |

## TOTAL ESTIMATED EFFORT

| Gap | Rego | Python | Schema/Config | Total |
|-----|------|--------|---------------|-------|
| GAP 1: Reg BI | — | ~800 | ~300 | ~1,100 |
| GAP 2: Liability | — | ~400 | ~300 | ~700 |
| GAP 3: WSP-YAML | ~200 | ~500 | ~300 | ~1,000 |
| GAP 4: BSA/AML | ~600 | ~400 | ~100 | ~1,100 |
| GAP 5: Account-Type | ~500 | ~300 | ~150 | ~950 |
| GAP 6: MNPI Scan | — | ~500 | ~50 | ~550 |
| GAP 7: Cross-Border | ~800 | ~500 | ~300 | ~1,600 |
| **TOTAL** | **~2,100** | **~3,400** | **~1,500** | **~7,000** |

~7,000 lines of new code/config across all 7 gaps, distributed across Phases 1–5.

---

*Document 4 of 4 — Project 007 v3 Architecture*
*Addressing LLMJ Committee v2 Reassessment: 7 Compliance Gap Technical Designs*
*July 2026*
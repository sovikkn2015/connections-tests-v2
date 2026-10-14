# Project 007: Railway Track Diagram

> Date: April 12, 2026
> What this is: The complete map of 007 — 7 tracks showing what exists, what plugs in, what must be built, how they connect, and where 006 feeds in.
> Key finding: Only 8 components (22%) must be built from scratch. 12 (33%) plug in as-is. 16 (44%) are adapted from existing systems. Total novel code: ~3,300 lines.

---

## Legend

```
  ████  = EXISTS (use as-is, plug and play)
  ░░░░  = ADAPT (exists but needs FSI wrapper / config)
  ╳╳╳╳  = BUILD (novel, does not exist anywhere)
```

---

## Track 1: Identity Layer — "Who Are You?"

```
       PLUG IN              ADAPT                BUILD
  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
  │ OAuth 2.0 /  │    │ A2A Agent    │    │ Agent Identity       │
  │ OpenID       │────│ Cards        │────│ Document (AID)       │
  │ Connect      │    │ (add FSI     │    │                      │
  │ ████████████ │    │  fields)     │    │ ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳ │
  │ (user auth)  │    │ ░░░░░░░░░░░░ │    │ (FSI: LEI, CRD,     │
  └──────────────┘    └──────────────┘    │  authority, revoke)  │
                                          └──────────────────────┘
```

## Track 2: Protocol Layer — "How Do We Talk?"

```
  PLUG IN         PLUG IN         PLUG IN         ADAPT
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐
  │ MCP      │   │ A2A      │   │ REST/gRPC│   │ FIX Bridge   │
  │ ████████ │   │ ████████ │   │ ████████ │   │ ░░░░░░░░░░░░ │
  └──────────┘   └──────────┘   └──────────┘   └──────────────┘
  Agent→Tool     Agent→Agent    Universal       OMS→Broker
```

## Track 3: Schema Layer — "What Does This Data Mean?"

```
  PLUG IN              BUILD                ADAPT (per system)
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
  │ FIX tags     │   │ Canonical    │   │ Schema Translators   │
  │ ISO 20022    │   │ FSI Data     │   │ SF↔Canon, Orion↔Canon│
  │ ████████████ │   │ Model        │   │ Aladdin↔Canon, etc.  │
  └──────────────┘   │ ╳╳╳╳╳╳╳╳╳╳ │   │ ░░░░░░░░░░░░░░░░░░░ │
                     └──────────────┘   └──────────────────────┘
```

## Track 4: Trust / Authority Layer — THE MOAT

```
  ADAPT                BUILD                BUILD
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
  │ Bedrock      │   │ Authority    │   │ MNPI Policy Engine   │
  │ Guardrails   │   │ Policy       │   │ Per-archetype,       │
  │ ░░░░░░░░░░░░ │   │ Engine       │   │ per-field, per-role  │
  ├──────────────┤   │ ╳╳╳╳╳╳╳╳╳╳ │   │ ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳ │
  │ Einstein     │   ├──────────────┤   ├──────────────────────┤
  │ Trust Layer  │   │ Delegation   │   │ Audit Logger (WORM)  │
  │ ░░░░░░░░░░░░ │   │ Engine       │   │ ░░░░░░░░░░░░░░░░░░░ │
  └──────────────┘   │ ╳╳╳╳╳╳╳╳╳╳ │   └──────────────────────┘
                     └──────────────┘
```

## Track 5: Semantic / Intent Layer — "What Do You Mean?"

```
  ADAPT              BUILD                PLUG IN
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
  │ FDC3 Intents │   │ FSI Intent   │   │ OpenClaw Intent      │
  │ (desktop)    │   │ Taxonomy     │   │ Router               │
  │ ░░░░░░░░░░░░ │   │ ╳╳╳╳╳╳╳╳╳╳ │   │ ████████████████████ │
  └──────────────┘   └──────────────┘   └──────────────────────┘
```

## Track 6: MCP Server Ecosystem — "The Adapters"

```
  PLUG IN (006)      ADAPT (vendor APIs)         BUILD (complex)
  ┌──────────────┐   ┌────────────────────────┐  ┌──────────────┐
  │ SEC EDGAR ██ │   │ Orion       ░░░░░░░░░░ │  │ FIX Bridge   │
  │ Market   ██ │   │ Schwab      ░░░░░░░░░░ │  │ ╳╳╳╳╳╳╳╳╳╳ │
  │ News     ██ │   │ Fidelity    ░░░░░░░░░░ │  ├──────────────┤
  │ SF FSC   ░░ │   │ Wealthbox   ░░░░░░░░░░ │  │ SWIFT Bridge │
  └──────────────┘   │ Bloomberg   ░░░░░░░░░░ │  │ ╳╳╳╳╳╳╳╳╳╳ │
                     │ SS&C Eze    ░░░░░░░░░░ │  └──────────────┘
                     │ + 10 more   ░░░░░░░░░░ │
                     └────────────────────────┘
  Every adapter inherits trust natively from Track 4.
```

## Track 7: Agent Runtime + Channels — "The User Interface"

```
  PLUG IN              PLUG IN              ADAPT
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
  │ OpenClaw     │   │ Channels     │   │ Pipeline Engine      │
  │ Gateway      │   │ (12+)        │   │ (from 006, made      │
  │ ████████████ │   │ ████████████ │   │  configurable)       │
  ├──────────────┤   │ Slack,Teams, │   │ ░░░░░░░░░░░░░░░░░░░ │
  │ Bedrock      │   │ WhatsApp,    │   └──────────────────────┘
  │ AgentCore    │   │ Telegram,etc │
  │ ████████████ │   └──────────────┘
  └──────────────┘
  007 does not replace OpenClaw. 007 adds the 5 interop layers underneath.
```

---

## How the Tracks Connect — A Single Request

User says: "Prep me for my meeting with Henderson tomorrow" on WhatsApp at 6am.

```
  USER (WhatsApp)
    |
    v
  TRACK 7: RUNTIME (OpenClaw Gateway + AgentCore)           PLUG
    |
    v
  TRACK 5: SEMANTIC ("prep me for Henderson")
           -> client.prep_meeting(client, date)              BUILD
    |
    v
  TRACK 1: IDENTITY (attach Agent Identity Document)
           agent=oc-007, user=sarah, firm=Acme               BUILD
    |
    v
  TRACK 4: TRUST (authority check)
           Can sarah access Henderson? -> YES
           Reg BI documentation required? -> YES             BUILD
    |
    v
  TRACK 3: SCHEMA (map intent to canonical types)
           Need: Client + Holdings + Performance             BUILD
    |
    v
  TRACK 2: PROTOCOL (MCP tools/call to each system)
           SF FSC -> SOQL, Orion -> REST, eMoney -> REST     PLUG
    |
    v
  TRACK 6: ADAPTERS (MCP servers call vendor APIs)
           Each inherits trust + schema natively             ADAPT
    |
    v
  TRACK 4: TRUST (post-call -- filter response)
           Strip MNPI per archetype policy
           Log audit entry (immutable)                       BUILD
    |
    v
  TRACK 3: SCHEMA (translate vendor response -> canonical)
           Orion Position -> canonical Holding               ADAPT
    |
    v
  TRACK 7: RUNTIME (LLM synthesizes, sends to user)
           Meeting prep brief -> WhatsApp                    PLUG
```

---

## Where 006 and 007 Overlap

006 is not thrown away. It becomes the first 007 deployment for Tier 3 wealth management.

### 006 contributes to 007:

| Track | What 006 Provides |
|-------|-------------------|
| Track 2 (Protocol) | MCP pattern (proven), 3 MCP servers, mcp-rest-bridge.mjs |
| Track 3 (Schema) | Salesforce IR_* objects (39 fields), seed data, FSC holdings |
| Track 4 (Trust) | MNPI filter (partial), compliance screening (basic), audit logging (dual-write), Bedrock Guardrails, Einstein Trust Layer |
| Track 5 (Semantic) | Pipeline engine (23 stages), AutoResearchClaw config, FSI prompts |
| Track 6 (Adapters) | Financial models (DCF, comps, Monte Carlo, stress test, portfolio impact, rebalance), MetaClaw |
| Track 7 (Runtime) | OpenClaw on AgentCore, adapter.js, frontend, channel configs, eval suite (150-query) |

### 006 does NOT contribute:

| Track | What Is Missing |
|-------|-----------------|
| Track 1 (Identity) | No agent identity (bearer token only) |
| Track 4 (Trust) | No authority engine, no delegation, no cross-boundary trust |
| Track 3 (Schema) | No canonical data model (hardcoded SF fields) |
| Track 5 (Semantic) | No intent taxonomy (implicit in pipeline) |

### The relationship:

```
  007 = 006 + 5 interoperability layers

  006 proved:  "It works for one archetype"
  007 proves:  "It works for any archetype"

  006 code:    ~12,400 lines
  007 adds:    ~3,300 lines (8 novel components)
  007 adapts:  ~5,000 lines (refactoring + vendor wrappers)

  006 is NOT thrown away.
  006 is PROMOTED into the first 007 deployment.
```

---

## The Build vs Plug vs Adapt Scorecard

| Component | PLUG | ADAPT | BUILD |
|-----------|:----:|:-----:|:-----:|
| **TRACK 1: IDENTITY** | | | |
| OAuth 2.0 / OIDC | ██ | | |
| A2A Agent Cards | | ░░ | |
| Agent Identity Document | | | ╳╳ |
| Revocation service | | | ╳╳ |
| **TRACK 2: PROTOCOL** | | | |
| MCP | ██ | | |
| A2A | ██ | | |
| REST / gRPC | ██ | | |
| FIX Bridge | | ░░ | |
| SWIFT/ISO 20022 Bridge | | ░░ | |
| Kafka Bridge | | ░░ | |
| **TRACK 3: SCHEMA** | | | |
| FIX tag dictionary | ██ | | |
| ISO 20022 schemas | ██ | | |
| Canonical FSI Data Model | | | ╳╳ |
| Schema translators (each) | | ░░ | |
| **TRACK 4: TRUST (THE MOAT)** | | | |
| Bedrock Guardrails | | ░░ | |
| Einstein Trust Layer | | ░░ | |
| Authority Policy Engine | | | ╳╳ |
| MNPI Policy Engine | | | ╳╳ |
| Delegation Engine | | | ╳╳ |
| Audit Logger (WORM) | | ░░ | |
| **TRACK 5: SEMANTIC** | | | |
| FDC3 intent vocabulary | | ░░ | |
| FSI Intent Taxonomy | | | ╳╳ |
| OpenClaw intent router | ██ | | |
| **TRACK 6: MCP ADAPTERS** | | | |
| SEC EDGAR (from 006) | ██ | | |
| Market Data (from 006) | ██ | | |
| News Search (from 006) | ██ | | |
| Salesforce FSC | | ░░ | |
| Tier 3/4 adapters (each) | | ░░ | |
| Tier 2 adapters (each) | | ░░ | |
| Tier 5 adapters (each) | | ░░ | |
| FIX Bridge | | | ╳╳ |
| SWIFT Bridge | | | ╳╳ |
| **TRACK 7: RUNTIME** | | | |
| OpenClaw Gateway | ██ | | |
| OpenClaw Channels (12+) | ██ | | |
| Bedrock AgentCore | ██ | | |
| Pipeline Engine | | ░░ | |
| **TOTALS** | **12 (33%)** | **16 (44%)** | **8 (22%)** |

---

## The 8 Things That Must Be Built From Scratch

| # | Component | Lines | Why Novel |
|---|-----------|-------|-----------|
| 1 | Agent Identity Document | ~300 | FSI agent identity with LEI, CRD, authority, delegation, revocation |
| 2 | Authority Policy Engine | ~500 | YAML-driven: (identity, action, target, context) -> decision |
| 3 | MNPI Policy Engine | ~400 | Per-archetype, per-field, per-role data sensitivity |
| 4 | Delegation Engine | ~300 | A delegates to B: B.auth = A intersect B.capability |
| 5 | Canonical FSI Data Model | ~200 | System-agnostic: Client, Holding, Order, Research, Compliance, Audit |
| 6 | FSI Intent Taxonomy | ~200 | research.*, client.*, compliance.*, execution.* |
| 7 | FIX Protocol MCP Bridge | ~800 | Stateful FIX in stateless MCP |
| 8 | SWIFT/ISO 20022 Bridge | ~600 | Payment/settlement in MCP |

Items 1-6 (~1,900 lines) are the NOVEL CONTRIBUTION.
Items 7-8 (~1,400 lines) are complex engineering but known problems.
Items 1-4 together ARE the moat.

Total new code: ~3,300 lines.

---

## Grand Total

```
  FROM SCRATCH (22%):    ~3,300 lines  (8 novel components)
  ADAPTED (44%):         ~5,000 lines  (006 refactoring + vendor wrappers)
  PLUG AND PLAY (33%):        0 lines  (already exists)

  TOTAL PLATFORM:       ~20,000 lines
  TRULY NOVEL:           ~3,300 lines  (16% of total)
```

# Project 007: Module Architecture & Interconnectivity

> Date: April 12, 2026
> What this is: The 13 buildable modules of 007, their boundaries, inputs/outputs, dependencies, and the full call flow showing how they connect for a single request.

---

## The 13 Modules

| # | Module | Type | Lines | What It Does |
|---|--------|------|-------|-------------|
| M1 | Agent Identity Service | BUILD | ~300 | Issues, verifies, revokes Agent Identity Documents |
| M2 | Authority Policy Engine | BUILD | ~500 | Evaluates (identity, action, target, context) to decision |
| M3 | Canonical Schema Registry | BUILD | ~1,700 | 18 system-agnostic FSI data types + field semantics (YAML + Python) |
| M4 | MNPI Policy Engine | BUILD | ~400 | Filters data per archetype, per field, per role |
| M5 | Enterprise Config Loader | ADAPT | ~200 | Reads enterprise-config.yaml, provides to all modules |
| M6 | Trust-Aware MCP Gateway | BUILD | ~600 | Central hub — every MCP call passes through, enforces trust |
| M7 | Schema Translators | ADAPT | ~100 each | Translates vendor data to/from canonical types (one per vendor) |
| M8 | Pipeline Engine | ADAPT | ~1,400 | Configurable multi-stage pipeline (from 006 pipeline.py) |
| M9 | FSI Intent Router | BUILD | ~300 | Maps natural language to structured FSI intents |
| M10 | Audit Logger | ADAPT | ~200 | Immutable dual-write audit trail (CRM + Langfuse + WORM) |
| M11 | MCP Server Adapters | ADAPT | ~200-800 each | Polyglot MCP servers wrapping vendor systems (TS + Python + gRPC) |
| M12 | Agent Runtime + Channels | PLUG IN | 0 | OpenClaw Gateway + Bedrock AgentCore + 12+ channels |
| M13 | FIX Protocol Bridge | BUILD | ~1,500-2,500 | Stateful FIX 4.2 TCP sessions wrapped in MCP (specialist contractor) |

Totals: 7 BUILD (~5,800+ lines), 5 ADAPT (~6,000+ lines), 1 PLUG IN (0 lines)

---

## Module Details

### M1: Agent Identity Service (BUILD ~300 lines)

Issues, verifies, and revokes Agent Identity Documents.

- Input: user credentials (OAuth), firm config
- Output: signed AID (JSON) with expiry + revocation URL
- Depends on: nothing (foundational)
- Used by: EVERY other module

### M2: Authority Policy Engine (BUILD ~500 lines)

Evaluates (identity, action, target, context) and returns a decision.

- Input: AID + requested action + target resource + context
- Output: ALLOW / DENY / REQUIRE_APPROVAL / ESCALATE
- Depends on: M1 (identity), M5 (enterprise config)
- Used by: M6 (MCP gateway), M8 (pipeline), M4 (MNPI)

### M3: Canonical Schema Registry (BUILD ~200 lines YAML)

Defines system-agnostic FSI data types and field semantics.

- Input: none (static definition)
- Output: type definitions (Client, Holding, Order, ResearchBrief, ComplianceCheck, AuditEntry, Household, TaxLot, Transaction, Balance, Performance, SecurityProfile, Quote, PlanSummary, Goal, InteractionSummary, ComplianceAlert, PaymentInstruction)
- Depends on: nothing (foundational)
- Used by: M7 (schema translators), M8 (pipeline), M9 (intent)

### M4: MNPI Policy Engine (BUILD ~400 lines)

Filters data per archetype, per field, per role.

- Input: raw data + AID (role, archetype) + field metadata
- Output: filtered data (MNPI fields stripped/redacted)
- Depends on: M1 (identity), M5 (enterprise config)
- Used by: M6 (MCP gateway — pre and post call filtering)

### M5: Enterprise Config Loader (ADAPT ~200 lines)

Reads enterprise-config.yaml, provides to all modules.

- Input: YAML file (one per enterprise deployment)
- Output: parsed config: archetype, systems, compliance regime, MNPI policy, channels, audit standard
- Depends on: nothing
- Used by: M2, M4, M6, M7, M8, M9

### M6: Trust-Aware MCP Gateway (BUILD ~600 lines)

Central hub. Every MCP call passes through. Enforces identity, authority, MNPI, audit.

- Input: MCP tools/call request + AID
- Output: filtered MCP response + audit log entry
- Depends on: M1 (identity verify), M2 (authority check), M4 (MNPI filter), M10 (audit logger)
- Used by: agent runtime (OpenClaw) — all MCP calls route here

### M7: Schema Translators (ADAPT ~100 lines each)

Translates vendor-specific data to/from canonical types.

- Input: vendor API response (Orion Position, SF Account, etc.)
- Output: canonical type (Holding, Client, etc.)
- Depends on: M3 (canonical schema)
- Used by: M11 (MCP server adapters)
- Count: one per vendor system (~15-20 translators)

### M8: Pipeline Engine (ADAPT ~1,400 lines, from 006)

Configurable multi-stage pipeline.

- Input: intent + AID + enterprise config
- Output: structured output (research brief, meeting prep, etc.)
- Depends on: M2 (authority at HITL gates), M5 (config), M6 (MCP gateway), M9 (intent mapping), M10 (audit)
- Used by: agent runtime when complex queries trigger pipeline

### M9: FSI Intent Router (BUILD ~300 lines)

Maps natural language to structured FSI intents.

- Input: user message + AID (role context)
- Output: structured intent (research.generate_brief, client.prep_meeting, etc.)
- Depends on: M1 (identity for role context), M5 (config)
- Used by: agent runtime — first stop after auth

### M10: Audit Logger (ADAPT ~200 lines, from 006)

Immutable dual-write audit trail.

- Input: action, AID, data accessed, compliance status, trace_id
- Output: writes to CRM + Langfuse + WORM archive
- Depends on: M1 (identity for who-did-what)
- Used by: M6 (every MCP call), M8 (every pipeline stage), M2 (every authority decision)

### M11: MCP Server Adapters (ADAPT ~200 lines each)

Individual MCP servers wrapping vendor systems.

- Input: MCP tools/call (canonical)
- Output: MCP response (canonical, via M7 translator)
- Depends on: M7 (schema translator for this vendor)
- Used by: M6 (MCP gateway routes calls to these)
- Count: 3 from 006 + ~15-20 new

Note (post-RES-08): M11 is polyglot. TypeScript for REST adapters, Python for BLPAPI (Bloomberg) and gRPC (Eze). SFTP batch ingestion for custodian daily files. See ARCH-09 for full sub-type breakdown.

### M12: Agent Runtime + Channels (PLUG IN)

OpenClaw Gateway + Bedrock AgentCore + 12+ channels.

- Input: user messages from any channel
- Output: agent responses to any channel
- Depends on: M9 (intent router), M6 (MCP gateway), M8 (pipeline engine)
- Note: we don't build this, we plug into it

---

## Interconnectivity Map

```
                         USER
                          |
                          v
                   +-----------+
                   | M12       | (OpenClaw + Channels)
                   | PLUG IN   |
                   +--+--+--+--+
                      |  |  |
            +---------+  |  +---------+
            |            |            |
            v            v            v
     +----------+  +---------+  +----------+
     | M9 INTENT|  | M8 PIPE |  | M6 MCP   |
     | ROUTER   |  | LINE    |  | GATEWAY   |
     | BUILD    |  | ADAPT   |  | BUILD     |
     +--+--+----+  +--+--+--+  +--+--+--+--+
        |  |          |  |        |  |  |
        |  |          |  |        |  |  +----------+
        |  |          |  |        |  |             |
        v  v          v  v        v  v             v
  +--------+    +--------+   +--------+      +--------+
  | M1     |    | M2     |   | M4     |      | M10    |
  | IDENT  |    | AUTH   |   | MNPI   |      | AUDIT  |
  | BUILD  |    | BUILD  |   | BUILD  |      | ADAPT  |
  +--------+    +---+----+   +---+----+      +--------+
                    |             |
                    v             v
               +--------+
               | M5     |
               | CONFIG |
               | ADAPT  |
               +--------+

        M6 (MCP Gateway) also calls down to:

                   +--------+
                   | M11    |
                   | MCP    |
                   | ADAPT  |
                   +---+----+
                       |
                       v
                   +--------+
                   | M7     |
                   | SCHEMA |
                   | ADAPT  |
                   +---+----+
                       |
                       v
                   +--------+
                   | M3     |
                   | CANON. |
                   | BUILD  |
                   +--------+
```

---

## Full Call Flow — One Request Through All Modules

"Prep me for my meeting with Henderson tomorrow"

```
M12 (Runtime)
 |  User message arrives on WhatsApp
 |
 +---> M1 (Identity)
 |     Issue AID: sarah.chen, advisor, tier3, acme_wm
 |
 +---> M9 (Intent Router)
 |     Input: message + AID
 |     Output: client.prep_meeting(client="Henderson", date=tomorrow)
 |
 +---> M2 (Authority)
 |     Input: AID + intent + target=Henderson
 |     Check: Is Henderson sarah's client? -> YES
 |     Output: ALLOW + require Reg BI documentation
 |
 +---> M8 (Pipeline)
 |     Pipeline config loaded from M5
 |     |
 |     +---> M6 (MCP Gateway) -- call 1: get client profile
 |     |     +---> M2 (Authority): recheck -> ALLOW
 |     |     +---> M11 (Adapter): Salesforce FSC
 |     |     |     +---> M7 (Translator): SF Account -> canonical Client
 |     |     |           +---> M3 (Schema): Client type definition
 |     |     +---> M4 (MNPI Filter): strip SSN, DOB per tier3
 |     |     +---> M10 (Audit): log data access
 |     |     +---> return: canonical Client (filtered)
 |     |
 |     +---> M6 (MCP Gateway) -- call 2: get holdings
 |     |     +---> M2: recheck -> ALLOW
 |     |     +---> M11 (Adapter): Orion Portfolio
 |     |     |     +---> M7: Orion Position -> canonical Holding
 |     |     +---> M4: tier3 = keep full holdings (retail)
 |     |     +---> M10: log data access
 |     |     +---> return: canonical Holding[] (filtered)
 |     |
 |     +---> M6 (MCP Gateway) -- call 3: get plan summary
 |     |     +---> M11 (Adapter): eMoney
 |     |     |     +---> M7: eMoney Plan -> canonical PlanSummary
 |     |     +---> M4: summary only, no raw plan to LLM
 |     |     +---> M10: log data access
 |     |     +---> return: canonical PlanSummary (filtered)
 |     |
 |     +---> LLM (Bedrock Claude) -- synthesize meeting prep
 |     |     Input: canonical Client + Holding[] + PlanSummary
 |     |     Output: meeting prep brief
 |     |
 |     +---> M10 (Audit): log LLM call + output
 |     +---> return: meeting prep brief
 |
 +---> M10 (Audit): log complete journey
 +---> M12 (Runtime): deliver brief -> WhatsApp
```

All 12 modules touched for a single request.

---

## Dependency Matrix

Who calls whom (row calls column):

```
          M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12 M13
  M1       .   .   .   .   .   .   .   .   .   .   .   .   .
  M2       *   .   .   .   *   .   .   .   .   .   .   .   .
  M3       .   .   .   .   .   .   .   .   .   .   .   .   .
  M4       *   .   .   .   *   .   .   .   .   .   .   .   .
  M5       .   .   .   .   .   .   .   .   .   .   .   .   .
  M6       *   *   .   *   .   .   .   .   .   *   *   .   *
  M7       .   .   *   .   .   .   .   .   .   .   .   .   .
  M8       .   *   .   .   *   *   .   .   .   *   .   .   .
  M9       *   .   .   .   *   .   .   .   .   .   .   .   .
  M10      *   .   .   .   .   .   .   .   .   .   .   .   .
  M11      .   .   .   .   .   .   *   .   .   .   .   .   .
  M12      .   .   .   .   .   *   .   *   *   .   .   .   .
  M13      .   .   .   .   .   .   .   .   .   .   .   .   .
```

Key observations:
- M1 (Identity) called by 5 modules — foundational
- M5 (Config) called by 4 modules — enterprise DNA
- M6 (MCP Gateway) calls 5 modules — central hub
- M3 and M5 call nothing — pure data
- M12 only calls M6, M8, M9 — clean interface

---

## Build Order

```
Phase 0: M3 (Schema) + M5 (Config)
         Pure data, no deps.

Phase 1: M1 (Identity) + M10 (Audit)
         Foundational services. Called by everything.

Phase 2: M2 (Authority) + M4 (MNPI)
         Trust layer. THE MOAT.

Phase 3: M6 (MCP Gateway)
         Central hub. Wires M1 + M2 + M4 + M10.

Phase 4: M7 (Translators) + M11 (Adapters) + M13 (FIX Bridge)
         Vendor connections. Start with 3 from 006.

Phase 5: M9 (Intent Router) + M8 (Pipeline)
         Intelligence layer.

Phase 6: M12 (Runtime)
         Plug in OpenClaw. Wire it up.
```

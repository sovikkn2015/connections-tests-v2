# Agentforce Deep Research

## Table of Contents

1. [What is Agentforce](#what-is-agentforce)
2. [Version History](#version-history)
3. [The Salesforce Agentforce 360 Unified Stack (3 Layers)](#the-salesforce-agentforce-360-unified-stack)
4. [Where Einstein Fits](#where-einstein-fits)
5. [Core Architecture](#core-architecture)
6. [Atlas Reasoning Engine](#atlas-reasoning-engine)
7. [How You Build Agents](#how-you-build-agents)
8. [How Builder Tools Connect](#how-the-builder-tools-connect)
9. [Key Features in Agentforce 3+](#key-features-in-agentforce-3)
10. [SFDX Project Code Structure](#sfdx-project-code-structure)
11. [Agent Script Language](#agent-script-language)
12. [Metadata Types Reference](#metadata-types-reference)
13. [Pricing](#pricing)
14. [Real-World Results](#real-world-results)
15. [Known Limitations & Criticisms](#known-limitations--criticisms)
16. [Competitive Landscape](#competitive-landscape)

---

## What is Agentforce

Agentforce is Salesforce's AI agent platform, launched in October 2024 and rapidly iterated through
multiple versions. It lets enterprises build, deploy, and manage autonomous AI agents that operate
directly within the Salesforce ecosystem. Think of it as "digital labor" — agents that can reason,
plan, and execute multi-step business tasks without constant human oversight.

Agentforce goes well beyond a chatbot. These are autonomous agents that understand context, reason
through complex requests, and execute end-to-end workflows across Sales Cloud, Service Cloud,
Marketing Cloud, and more. They can qualify leads, resolve customer issues, schedule appointments,
generate proposals, and escalate when needed — all on their own.

As of late 2025, Agentforce had surpassed 12,000 enterprise customers and generated over $500M in
quarterly recurring revenue.
([source](https://cirra.ai/articles/salesforce-agentforce-3-ai-agents))

---

## Version History

| Version | Release    | Highlights                                                                 |
|---------|------------|----------------------------------------------------------------------------|
| 1.0     | Oct 2024   | Initial GA — autonomous agents within Salesforce Clouds                    |
| 2.0     | Dec 2024   | Atlas reasoning engine v1, Slack/Tableau skills, MuleSoft integration      |
| 2DX     | Mar 2025   | Multi-step proactive agents, smarter context handling                      |
| 3.0     | June 2025  | Command Center (observability), MCP support, 100+ industry actions, Atlas 3.0 |
| 360     | Oct 2025   | Unified "Agentic Enterprise" platform, deep Slack/ChatGPT/Claude integration |

---

## The Salesforce Agentforce 360 Unified Stack

At Dreamforce 2025, Salesforce rebranded everything under "Agentforce 360." The old Cloud names
map into three unified layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                     AGENTFORCE 360 PLATFORM                                 │
│                  (The Unified Salesforce Stack)                              │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                                                                             │
│   LAYER 3: CUSTOMER 360 APPS                                                │
│   (Where business data lives & users work)                                  │
│                                                                             │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│   │  Agentforce  │ │  Agentforce  │ │  Agentforce  │ │  Agentforce  │      │
│   │    Sales     │ │   Service    │ │  Marketing   │ │   Commerce   │      │
│   │ (was Sales   │ │ (was Service │ │ (was Mktg    │ │ (was Commerce│      │
│   │   Cloud)     │ │   Cloud)     │ │   Cloud)     │ │   Cloud)     │      │
│   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘      │
│          │                │                │                │               │
│   ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐      │
│   │  Agentforce  │ │  Agentforce  │ │              │ │              │      │
│   │   Health     │ │  Financial   │ │   Tableau    │ │    Slack     │      │
│   │ (was Health  │ │  Services    │ │              │ │  (Agentic    │      │
│   │   Cloud)     │ │              │ │              │ │     OS)      │      │
│   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘      │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                                                                             │
│   LAYER 2: AGENTFORCE PLATFORM                                              │
│   (AI reasoning, agent runtime, builder tools)                              │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                     │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │            ATLAS REASONING ENGINE                           │   │   │
│   │   │   Perceive ──▶ Plan ──▶ Execute ──▶ Reflect ──▶ (loop)     │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                     │   │
│   │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │   │
│   │   │ Agent Builder │ │   Prompt     │ │    Model     │               │   │
│   │   │ (Topics,     │ │   Builder    │ │   Builder    │               │   │
│   │   │  Actions,    │ │ (Templates,  │ │ (BYOM, LLM  │               │   │
│   │   │  Instructions│ │  Merge Fields│ │  Selection)  │               │   │
│   │   │  Guardrails) │ │  Grounding)  │ │              │               │   │
│   │   └──────────────┘ └──────────────┘ └──────────────┘               │   │
│   │                                                                     │   │
│   │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │   │
│   │   │  Flow        │ │    Apex      │ │  MCP Gateway │               │   │
│   │   │  Builder     │ │  (Custom     │ │  (MuleSoft   │               │   │
│   │   │ (Automation  │ │   Actions,   │ │   Connectors,│               │   │
│   │   │  Workflows)  │ │  @Invocable) │ │   Heroku)    │               │   │
│   │   └──────────────┘ └──────────────┘ └──────────────┘               │   │
│   │                                                                     │   │
│   │   ┌──────────────┐ ┌──────────────┐                                │   │
│   │   │  Testing     │ │  Command     │                                │   │
│   │   │  Center      │ │  Center      │                                │   │
│   │   │ (Simulation, │ │ (Observ-     │                                │   │
│   │   │  Evaluation) │ │  ability)    │                                │   │
│   │   └──────────────┘ └──────────────┘                                │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                                                                             │
│   LAYER 1: DATA 360                                                         │
│   (Unified data foundation — was Data Cloud)                                │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                     │   │
│   │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │   │
│   │  │  Unified   │ │  RAG       │ │  Vector    │ │  Zero-Copy │      │   │
│   │  │  Customer  │ │  Indexing & │ │  Search &  │ │  Data      │      │   │
│   │  │  Profiles  │ │  Chunking  │ │  Embeddings│ │  Federation│      │   │
│   │  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │   │
│   │                                                                     │   │
│   │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │   │
│   │  │  Real-Time │ │  Metadata  │ │  Knowledge │ │  External  │      │   │
│   │  │  Events &  │ │  Harmoniz- │ │  Articles  │ │  Sources   │      │   │
│   │  │  Streaming │ │  ation     │ │  & Vectors │ │  ERP/IoT   │      │   │
│   │  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                                                                             │
│   FOUNDATION: EINSTEIN TRUST LAYER + HYPERFORCE                             │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  Data Masking │ Toxicity Detection │ Zero Data Retention │ Audit   │   │
│   │  PII Protection │ Prompt Injection Defense │ FedRAMP │ SSO/RBAC   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Where Einstein Fits

Einstein isn't a separate layer — it's the umbrella brand for all AI/ML capabilities woven across
the stack. Here's how it maps:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    EINSTEIN = Salesforce AI Brand                            │
│            (Umbrella across the entire Agentforce 360 stack)                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  EINSTEIN CAPABILITIES BY CATEGORY                                    │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PREDICTIVE AI  (Classic Einstein)                              │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Einstein Lead Scoring        ──▶ Lives in Agentforce Sales   │  │  │
│  │  │  • Einstein Opportunity Scoring  ──▶ Lives in Agentforce Sales   │  │  │
│  │  │  • Einstein Case Classification  ──▶ Lives in Agentforce Service │  │  │
│  │  │  • Einstein Prediction Builder   ──▶ Lives in Platform Layer     │  │  │
│  │  │  • Einstein Discovery (Analytics)──▶ Lives in Tableau            │  │  │
│  │  │  • Einstein Activity Capture     ──▶ Lives in Agentforce Sales   │  │  │
│  │  │                                                                 │  │  │
│  │  │  Role: Historical pattern analysis, scoring, forecasting        │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  GENERATIVE AI  (Einstein GPT / Einstein 1 Studio)              │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Prompt Builder     ──▶ Create reusable prompt templates      │  │  │
│  │  │                           grounded in CRM data (merge fields,   │  │  │
│  │  │                           flows, apex). Used by agents & humans │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Model Builder      ──▶ Bring Your Own Model (BYOM),         │  │  │
│  │  │                           select LLMs (OpenAI, Claude, Gemini)  │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Copilot Builder    ──▶ Now evolved into Agent Builder        │  │  │
│  │  │    (legacy name)          (Topics, Actions, Instructions)       │  │  │
│  │  │                                                                 │  │  │
│  │  │  Role: Content generation, summarization, agent action creation │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  AGENTIC AI  (Agentforce — the newest evolution)                │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Atlas Reasoning Engine  ──▶ System-2 reasoning, planning     │  │  │
│  │  │  • Agent Builder           ──▶ Topics + Actions + Instructions  │  │  │
│  │  │  • Autonomous Agents       ──▶ Act independently, self-correct  │  │  │
│  │  │  • Multi-Agent Orchestration──▶ Agent-to-agent via MCP          │  │  │
│  │  │  • Einstein Copilot        ──▶ Now "Agentforce Assistant"       │  │  │
│  │  │    (human-in-the-loop)         (conversational AI interface)    │  │  │
│  │  │                                                                 │  │  │
│  │  │  Role: Autonomous task execution, reasoning, orchestration      │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  EINSTEIN TRUST LAYER  (Cuts across everything)                 │  │  │
│  │  │                                                                 │  │  │
│  │  │  Every AI call — predictive, generative, or agentic — passes   │  │  │
│  │  │  through this layer:                                            │  │  │
│  │  │                                                                 │  │  │
│  │  │  Prompt ──▶ [Data Masking] ──▶ [Toxicity Check] ──▶ LLM       │  │  │
│  │  │    ──▶ [Response Validation] ──▶ [Audit Log] ──▶ Output        │  │  │
│  │  │                                                                 │  │  │
│  │  │  • Zero data retention with LLM providers                       │  │  │
│  │  │  • PII masking / de-identification                              │  │  │
│  │  │  • Prompt injection defense                                     │  │  │
│  │  │  • Toxicity & hallucination detection                           │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Architecture

Three pillars power Agentforce:

1. **Atlas Reasoning Engine** — the "brain." Uses System-2 inference-time reasoning (ReAct
   prompting, vector search, feedback loops) rather than simple pattern matching. It plans,
   reflects, and self-corrects. Atlas 3.0 is 50% faster than prior versions, supports streamed
   output, web search with inline citations, and multi-LLM backends (OpenAI, Anthropic Claude,
   soon Google Gemini). It automatically fails over to backup models if one goes down. Achieved
   FedRAMP High certification for government use.
   ([source](https://engineering.salesforce.com/inside-the-brain-of-agentforce-revealing-the-atlas-reasoning-engine/))

2. **Data 360** (formerly Customer 360 / Data Cloud) — the data layer. Powers RAG (retrieval
   augmented generation), agent analytics, and bring-your-own-model capabilities. All customer
   and transactional data from ERP, IoT, and external sources gets harmonized here, giving
   agents a unified 360° view.

3. **Metadata Infrastructure** — enables agents to interpret business processes, schemas, and
   record logic natively within Salesforce.

Each agent is defined by five attributes:

- **Role** — purpose/job
- **Data** — knowledge it can access
- **Actions** — tasks it can perform
- **Guardrails** — boundaries and restrictions
- **Channel** — where/how it operates

---

## Atlas Reasoning Engine

The Atlas Reasoning Engine is the core "brain" of Agentforce. It uses advanced techniques to mimic
human-like "System-2" reasoning.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGENTFORCE PLATFORM                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        CHANNELS (User Touchpoints)                    │  │
│  │   [ Web Chat ]  [ Slack ]  [ WhatsApp ]  [ Voice ]  [ Mobile ]  [ API ]│ │
│  └──────────────────────────────┬────────────────────────────────────────┘  │
│                                 │                                           │
│                                 ▼                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    ATLAS REASONING ENGINE (The Brain)                  │  │
│  │                                                                       │  │
│  │   ┌─────────────────────────────────────────────────────────────┐     │  │
│  │   │  System-2 Reasoning Loop                                    │     │  │
│  │   │                                                             │     │  │
│  │   │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐ │     │  │
│  │   │   │ PERCEIVE │──▶│   PLAN   │──▶│ EXECUTE  │──▶│REFLECT │ │     │  │
│  │   │   │          │   │          │   │          │   │        │ │     │  │
│  │   │   │ Parse    │   │ ReAct    │   │ Call     │   │Evaluate│ │     │  │
│  │   │   │ Intent   │   │ Prompting│   │ Actions  │   │Results │ │     │  │
│  │   │   │ Context  │   │ Strategy │   │ Tools    │   │Self-Fix│ │     │  │
│  │   │   └──────────┘   └──────────┘   └──────────┘   └───┬────┘ │     │  │
│  │   │                                                     │      │     │  │
│  │   │                       ◀────── Feedback Loop ────────┘      │     │  │
│  │   └─────────────────────────────────────────────────────────────┘     │  │
│  │                                                                       │  │
│  │   Multi-LLM Backend:  [ OpenAI ]  [ Anthropic Claude ]  [ Gemini ]   │  │
│  │   Features: Streaming Output │ Auto-Failover │ RAG │ Citations       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│          ┌───────────────────────┼───────────────────────┐                  │
│          ▼                       ▼                       ▼                  │
│  ┌──────────────┐   ┌───────────────────┐   ┌───────────────────────┐      │
│  │  DATA 360    │   │  MCP GATEWAY      │   │  COMMAND CENTER       │      │
│  │              │   │  (Interop Layer)  │   │  (Observability)      │      │
│  │ CRM Data     │   │ MuleSoft          │   │ Real-Time Dash        │      │
│  │ Knowledge    │   │ Connectors        │   │ Agent Health          │      │
│  │ Vectors      │   │ Agent Gateway     │   │ Session Replay        │      │
│  │ Profiles     │   │ Identity &        │   │ Cost Metrics          │      │
│  │ Events       │   │ Policies          │   │ OpenTelemetry         │      │
│  │ External     │   │ Heroku MCP        │   │ ──▶ Datadog/Splunk   │      │
│  └──────────────┘   └───────────────────┘   └───────────────────────┘      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  TRUST & GOVERNANCE                                                   │  │
│  │  Hyperforce Security │ FedRAMP High │ Zero-Trust Agent Identity │ RBAC│  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Atlas Technical Details

- Built with asynchronous, event-driven, graph-based workflows and concurrent design principles
- Employs cooperative agent swarms for multi-agent orchestration
- Generic agents are composed of three key components:
  - **State**: Short-term and long-term memory for retaining past interactions and user data
  - **Flow**: Logical framework guiding an agent's actions and next steps
  - **Side Effects**: Actions performed to impact the environment (updating records, initiating tasks)
- Early pilots demonstrated a 2x increase in response relevance and 33% increase in end-to-end
  accuracy compared to competitors' solutions
- Atlas 3.0 uses a declarative approach with YAML configuration files for agent creation
- Asynchronous publish-subscribe event-driven architecture for scalability
- Modular design where each module is a self-contained service communicating through strongly
  typed interfaces

([source](https://engineering.salesforce.com/inside-the-brain-of-agentforce-revealing-the-atlas-reasoning-engine/))

---

## How You Build Agents

The developer workflow uses Agent Builder:

1. **Define Topics** — categories that organize an agent's capabilities (e.g., "Order Management,"
   "Patient Scheduling"). Topics include classification descriptions and scope written in natural
   language.

2. **Create Actions** — the actual tasks. Built using:
   - Flows (low-code)
   - Apex classes (code, using `@InvocableMethod` / `@InvocableVariable`)
   - Prompt Templates
   - MCP connectors (for external services)

3. **Write Instructions** — natural language guidance for the Atlas engine on how to orchestrate
   actions, handle edge cases, and make decisions.

4. **Test** — an integrated Testing Center simulates agent activity at volume before going live.

You can also use the Agentforce Python SDK to create and deploy agents programmatically, or describe
behaviors in natural language and auto-generate topics, instructions, and test cases.

([source](https://developer.salesforce.com/blogs/2025/01/how-to-write-effective-natural-language-instructions-for-agentforce))

---

## How the Builder Tools Connect

This shows the developer/admin toolchain and how each tool feeds into agents:

```
                         ┌─────────────────────┐
                         │    USER / ADMIN /    │
                         │     DEVELOPER        │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
          │ FLOW BUILDER│ │   PROMPT    │ │  APEX (Code)    │
          │             │ │  BUILDER    │ │                 │
          │ Visual low- │ │             │ │ @InvocableMethod│
          │ code auto-  │ │ Reusable    │ │ @InvocableVar   │
          │ mation.     │ │ prompt      │ │                 │
          │ Screen flows│ │ templates   │ │ Custom business │
          │ Auto-launch │ │ grounded in │ │ logic, callouts │
          │ Record-trig │ │ CRM data    │ │ DML, SOQL       │
          │ Scheduled   │ │ (merge      │ │                 │
          │             │ │  fields,    │ │                 │
          │             │ │  related    │ │                 │
          │             │ │  lists)     │ │                 │
          └──────┬──────┘ └──────┬──────┘ └────────┬────────┘
                 │               │                  │
                 │   All three become               │
                 └───────────┐  │  ┌────────────────┘
                             ▼  ▼  ▼
                    ┌─────────────────────┐
                    │   AGENT ACTIONS     │
                    │                     │
                    │  Each action has:   │
                    │  • Input schema     │
                    │  • Output schema    │
                    │  • Description      │
                    │    (for Atlas to    │
                    │     understand)     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      TOPICS         │
                    │                     │
                    │  Group actions by   │
                    │  domain:            │
                    │  • Order Management │
                    │  • Lead Qualification│
                    │  • Patient Support  │
                    │                     │
                    │  Each topic has:    │
                    │  • Classification   │
                    │    description      │
                    │  • Scope rules      │
                    │  • Instructions     │
                    │    (natural lang)   │
                    └──────────┬──────────┘
                               │
                               ▼
          ┌────────────────────────────────────────┐
          │         ATLAS REASONING ENGINE          │
          │                                        │
          │  User message arrives                  │
          │       │                                │
          │       ▼                                │
          │  ┌──────────┐    Classify which        │
          │  │ CLASSIFY │──▶ topic(s) apply        │
          │  └──────────┘                          │
          │       │                                │
          │       ▼                                │
          │  ┌──────────┐    Read instructions,    │
          │  │   PLAN   │──▶ pick actions,         │
          │  └──────────┘    determine order        │
          │       │                                │
          │       ▼                                │
          │  ┌──────────┐    Run the Flow /        │
          │  │ EXECUTE  │──▶ Apex / Prompt /       │
          │  └──────────┘    MCP call              │
          │       │                                │
          │       ▼                                │
          │  ┌──────────┐    Check result,         │
          │  │ EVALUATE │──▶ self-correct or       │
          │  └──────────┘    respond to user       │
          │       │                                │
          │       ▼                                │
          │  [Response or next action loop]        │
          │                                        │
          └──────────────────┬─────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌───────────┐ ┌────────────┐
     │   DATA 360   │ │   MCP     │ │  EINSTEIN  │
     │              │ │  GATEWAY  │ │   TRUST    │
     │ CRM Records  │ │           │ │   LAYER    │
     │ Knowledge    │ │ External  │ │            │
     │ Vectors      │ │ APIs,     │ │ Every call │
     │ Profiles     │ │ Heroku,   │ │ is masked, │
     │ Events       │ │ Partner   │ │ validated, │
     │              │ │ Services  │ │ audited    │
     └──────────────┘ └───────────┘ └────────────┘
```

---

## Key Features in Agentforce 3+

- **Command Center**: Real-time dashboards for agent adoption, health (latency, errors), topic
  performance, cost metrics. Session replay, AI-generated improvement recommendations. All
  activity logged via OpenTelemetry, exportable to Datadog/Splunk.
  ([source](https://salesforce.com/news/press-releases/2025/06/23/agentforce-3-announcement))

- **Model Context Protocol (MCP)**: Open standard for agent interoperability — called "USB-C for
  AI agents." Lets agents securely call external tools, APIs, and other agents. MuleSoft
  connectors auto-publish internal APIs as agent-friendly actions. Slack natively adopted MCP.
  ([source](https://developer.salesforce.com/blogs/2025/06/introducing-mcp-support-across-salesforce))

- **Unified Agent Gateway**: MuleSoft-managed registry where admins assign agent identities,
  roles, and policies. Enforces least-privilege access.

- **AgentExchange Marketplace**: 100+ prebuilt industry-specific actions (patient scheduling,
  vehicle service reminders, ad proposal generation). Partners include AWS, Google, Cisco, IBM,
  PayPal, Stripe, Box.

- **Agentforce Voice**: AI-powered voice across phone, web, and mobile with real-time CRM data
  access.

- **Multi-LLM Support**: Choose between OpenAI, Anthropic Claude (via AWS Bedrock), with Google
  Gemini coming. Automatic failover between models.

---

## SFDX Project Code Structure

This is how an Agentforce project looks on disk in a Salesforce DX project:

```
my-agentforce-project/
│
├── sfdx-project.json                          # Project config
├── .forceignore
│
└── force-app/
    └── main/
        └── default/
            │
            │  ══════════════════════════════════════════════════
            │  AGENT DEFINITION (New: Agent Script / Authoring Bundle)
            │  ══════════════════════════════════════════════════
            │
            ├── aiAuthoringBundles/
            │   └── My_Service_Agent/
            │       ├── My_Service_Agent.bundle-meta.xml   # Bundle metadata
            │       └── My_Service_Agent.agent             # Agent Script file
            │                                               # (YAML-like DSL with
            │                                               #  config, system, topics,
            │                                               #  actions, variables)
            │
            │  ══════════════════════════════════════════════════
            │  AGENT PLANNER (Reasoning Engine Config)
            │  ══════════════════════════════════════════════════
            │
            ├── genAiPlannerBundles/
            │   └── My_Service_Agent.genAiPlannerBundle-meta.xml
            │       # Links Bot + Topics + Actions into one reasoning unit
            │       # Defines LLM strategy, planner type
            │
            │  ══════════════════════════════════════════════════
            │  TOPICS (GenAiPlugin)
            │  ══════════════════════════════════════════════════
            │
            ├── genAiPlugins/
            │   ├── Order_Management.genAiPlugin-meta.xml
            │   │   # <GenAiPlugin>
            │   │   #   <masterLabel>Order Management</masterLabel>
            │   │   #   <description>Handles order status, returns...</description>
            │   │   #   <genAiPluginInstructions>
            │   │   #     <instruction>Always verify order number...</instruction>
            │   │   #   </genAiPluginInstructions>
            │   │   # </GenAiPlugin>
            │   │
            │   └── Lead_Qualification.genAiPlugin-meta.xml
            │
            │  ══════════════════════════════════════════════════
            │  ACTIONS (GenAiFunction)
            │  ══════════════════════════════════════════════════
            │
            ├── genAiFunctions/
            │   ├── Get_Order_Status.genAiFunction-meta.xml
            │   │   # <GenAiFunction>
            │   │   #   <masterLabel>Get Order Status</masterLabel>
            │   │   #   <description>Retrieves current order status</description>
            │   │   #   <genAiFunctionInputs>
            │   │   #     <input><name>orderId</name><type>string</type></input>
            │   │   #   </genAiFunctionInputs>
            │   │   #   <genAiFunctionOutputs>...</genAiFunctionOutputs>
            │   │   #   <actionReference>Get_Order_Status_Flow</actionReference>
            │   │   # </GenAiFunction>
            │   │
            │   ├── Create_Return_Label.genAiFunction-meta.xml
            │   └── Qualify_Lead.genAiFunction-meta.xml
            │
            │  ══════════════════════════════════════════════════
            │  PROMPT TEMPLATES (GenAiPromptTemplate)
            │  ══════════════════════════════════════════════════
            │
            ├── genAiPromptTemplates/
            │   └── Summarize_Case.genAiPromptTemplate-meta.xml
            │       # Reusable prompt template with merge fields
            │       # Can be invoked from Flows, Apex, or as agent actions
            │
            │  ══════════════════════════════════════════════════
            │  BOT (Top-level Einstein Bot wrapper)
            │  ══════════════════════════════════════════════════
            │
            ├── bots/
            │   └── My_Service_Agent/
            │       ├── My_Service_Agent.bot-meta.xml       # Top-level bot definition
            │       └── v1.botVersion-meta.xml              # Bot version config
            │           # Bot + BotVersion = simple chatbot
            │           # Bot + BotVersion + GenAiPlannerBundle = AGENT
            │
            │  ══════════════════════════════════════════════════
            │  SUPPORTING CODE (Flows, Apex, LWC)
            │  ══════════════════════════════════════════════════
            │
            ├── flows/
            │   ├── Get_Order_Status_Flow.flow-meta.xml     # Flow-based action
            │   └── Create_Return_Label_Flow.flow-meta.xml
            │
            ├── classes/
            │   ├── LeadQualifier.cls                       # Apex action
            │   ├── LeadQualifier.cls-meta.xml              # (@InvocableMethod)
            │   ├── OrderService.cls
            │   └── OrderService.cls-meta.xml
            │
            ├── lwc/                                        # Lightning Web Components
            │   └── agentChatWidget/                        # (optional UI)
            │
            │  ══════════════════════════════════════════════════
            │  SETTINGS & PERMISSIONS
            │  ══════════════════════════════════════════════════
            │
            ├── settings/
            │   └── EinsteinGpt.settings-meta.xml           # Einstein GPT org settings
            │
            └── permissionsets/
                └── Agentforce_User.permissionset-meta.xml
                    # Required permission set licenses:
                    # - Agentforce (Default)
                    # - Agentforce Service Agent Builder
                    # - Einstein Prompt Templates
                    # - Prompt Template Manager
```

### How Metadata Types Link Together

```
┌──────────────────────────────────────────────────────────────────────┐
│                     METADATA DEPENDENCY GRAPH                        │
│                                                                      │
│                        ┌──────────────┐                              │
│                        │     Bot      │  (Top-level Einstein Bot)    │
│                        └──────┬───────┘                              │
│                               │                                      │
│                        ┌──────▼───────┐                              │
│                        │  BotVersion  │  (Version config)            │
│                        └──────┬───────┘                              │
│                               │                                      │
│                  ┌────────────▼─────────────┐                        │
│                  │  GenAiPlannerBundle      │  (Reasoning engine)    │
│                  │                          │                        │
│                  │  • LLM strategy          │                        │
│                  │  • Planner type          │                        │
│                  │  • Links topics & actions│                        │
│                  └────────────┬─────────────┘                        │
│                               │                                      │
│              ┌────────────────┼────────────────┐                     │
│              │                │                │                     │
│       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐              │
│       │ GenAiPlugin │ │ GenAiPlugin │ │ GenAiPlugin │  (Topics)    │
│       │ (Topic A)   │ │ (Topic B)   │ │ (Topic C)   │              │
│       │             │ │             │ │             │              │
│       │ •masterLabel│ │ •description│ │ •scope      │              │
│       │ •description│ │ •instruction│ │ •instruction│              │
│       │ •scope      │ │ •actions    │ │ •actions    │              │
│       │ •instruction│ │             │ │             │              │
│       └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│              │               │               │                      │
│       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐              │
│       │GenAiFunction│ │GenAiFunction│ │GenAiFunction│  (Actions)   │
│       │ (Action 1)  │ │ (Action 2)  │ │ (Action 3)  │              │
│       │             │ │             │ │             │              │
│       │ •description│ │ •inputs     │ │ •outputs    │              │
│       │ •inputs     │ │ •outputs    │ │ •actionRef  │              │
│       │ •outputs    │ │ •actionRef  │ │             │              │
│       │ •actionRef  │ │             │ │             │              │
│       └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│              │               │               │                      │
│              ▼               ▼               ▼                      │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────┐         │
│  │  Flow         │ │  Apex Class    │ │ GenAiPrompt       │         │
│  │  (.flow-meta) │ │  (.cls)        │ │ Template          │         │
│  │               │ │  @Invocable    │ │ (.genAiPrompt     │         │
│  │               │ │  Method        │ │  Template-meta)   │         │
│  └───────────────┘ └────────────────┘ └──────────────────┘         │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

  Bot + BotVersion                    = Simple Chatbot
  Bot + BotVersion + GenAiPlannerBundle = AGENT (with reasoning)
```

---

## Agent Script Language

Agent Script is Salesforce's new declarative scripting language (DSL) for building Agentforce
agents. Announced at Dreamforce 2025, it's a YAML-like syntax that combines natural language
instructions with programmatic expressions.

### Key Characteristics

- Indentation-based (like Python) — 3 spaces per level
- Human-readable, designed for non-developers to understand
- Combines LLM flexibility with deterministic business logic
- `instructions:->` with `|` for multiline prompt templates
- `if/else` conditions, variable assignment, transitions
- Comments with `#`

### Agent Script Block Types

| Block          | Purpose                                                    |
|----------------|------------------------------------------------------------|
| `config`       | Agent metadata: name, label, description, agent_type       |
| `system`       | Global settings: welcome/error messages, system instructions|
| `variables`    | Global variables accessible via `@variables.<name>`        |
| `language`     | Supported languages                                        |
| `connection`   | External connections (e.g., Enhanced Chat, escalation)     |
| `start_agent`  | Entry point / topic selector — routes to topics            |
| `topic`        | Instructions, logic, and actions for a specific domain     |

### Example: Hello World Agent Script

```agentscript
# ─── Config Block ───────────────────────────────────────
config:
   agent_name: "HelloWorld_Agent"
   agent_label: "HelloWorld Agent"
   description: "A minimal agent that greets users"

# ─── System Block ───────────────────────────────────────
system:
   messages:
      welcome: "Hello! I'm a simple agent here to say hi."
      error: "Sorry, I encountered an error."
   instructions: "You are a friendly assistant who warmly greets users."

# ─── Start Agent (Topic Selector / Entry Point) ────────
start_agent topic_selector:
   description: "Welcome users and begin friendly conversation"

   reasoning:
      instructions:|
         Select the tool that best matches the user's message
         and conversation history. If it's unclear, make your best guess.
      actions:
         begin_greeting: @utils.transition to @topic.greeting
            description: "Start the greeting conversation"

# ─── Topic Block ────────────────────────────────────────
topic greeting:
   description: "Greets the user and engages in friendly conversation"

   reasoning:
      instructions:->
         | Greet the user warmly and ask how you can help them.
           Always answer in the style of a poem.
```

### More Realistic Example: Order Management Agent

```agentscript
config:
   agent_name: "Order_Service_Agent"
   agent_label: "Order Service Agent"
   description: "Handles order inquiries, returns, and status checks"
   default_agent_user: "ServiceAgentUser"
   agent_type: AgentforceServiceAgent

system:
   messages:
      welcome: "Hi {!@variables.userPreferredName}! How can I help with your order?"
      error: "I'm sorry, something went wrong. Let me connect you with a human agent."
   instructions: |
      You are a helpful order management assistant for Acme Corp.
      Always verify the customer's identity before sharing order details.
      Be concise and professional.

variables:
   orderId:
      type: string
      description: "The current order ID being discussed"
   customerVerified:
      type: boolean
      description: "Whether the customer has been verified"
      default: false

start_agent topic_selector:
   description: "Route customer to the right topic based on their request"

   reasoning:
      instructions:|
         Analyze the customer message. Route to the appropriate topic.
         If the customer wants to check an order, go to order_status.
         If they want to return something, go to returns.
      actions:
         go_to_orders: @utils.transition to @topic.order_status
            description: "Customer wants to check order status"
         go_to_returns: @utils.transition to @topic.returns
            description: "Customer wants to initiate a return"

topic order_status:
   description: "Handles order status inquiries and tracking"

   actions:
      get_order:
         description: "Look up order status by order ID"
         target: flow://Get_Order_Status_Flow
         inputs:
            orderId:
               type: string
               description: "The order ID to look up"
         outputs:
            orderStatus:
               type: string
               description: "Current status of the order"
            estimatedDelivery:
               type: string
               description: "Estimated delivery date"

   reasoning:
      instructions:->
         | First, ask the customer for their order number.
         if @variables.customerVerified == false
            | Before proceeding, verify the customer's identity
              by asking for their email address.
         | Once verified, use the get_order action to retrieve status.
         | Share the order status and estimated delivery date.
         | Ask if there's anything else you can help with.
      actions:
         get_order: @action.get_order
            description: "Retrieve order status"

topic returns:
   description: "Handles return requests and label generation"

   actions:
      create_return:
         description: "Create a return label for the customer"
         target: apex://ReturnService.createReturnLabel
         inputs:
            orderId:
               type: string
               description: "Order ID for the return"
         outputs:
            returnLabel:
               type: string
               description: "URL to the return shipping label"

   reasoning:
      instructions:->
         | Ask the customer for their order number and reason for return.
         if @variables.customerVerified == false
            | Verify the customer's identity first.
         | Use create_return to generate a return label.
         | Provide the return label link and instructions.
      actions:
         create_return: @action.create_return
            description: "Generate return shipping label"
```

([source](https://developer.salesforce.com/docs/ai/agentforce/guide/ascript-blocks.html),
[source](https://developer.salesforce.com/sample-apps/agent-script-recipes/getting-started/hello-world-agent))

---

## Metadata Types Reference

| Metadata Type            | API Name                | What It Represents                          | Directory in SFDX                |
|--------------------------|-------------------------|---------------------------------------------|----------------------------------|
| Authoring Bundle         | `AiAuthoringBundle`     | Agent blueprint (Agent Script file)         | `aiAuthoringBundles/`            |
| Agent Planner            | `GenAiPlannerBundle`    | Reasoning engine config (links everything)  | `genAiPlannerBundles/`           |
| Topic                    | `GenAiPlugin`           | Category of actions (scope + instructions)  | `genAiPlugins/`                  |
| Action                   | `GenAiFunction`         | Individual task (inputs/outputs/target)     | `genAiFunctions/`                |
| Prompt Template          | `GenAiPromptTemplate`   | Reusable prompt with merge fields           | `genAiPromptTemplates/`          |
| Bot                      | `Bot`                   | Top-level Einstein Bot wrapper              | `bots/`                          |
| Bot Version              | `BotVersion`            | Version config for the bot                  | `bots/<name>/`                   |

### Required Permission Set Licenses

- Agentforce (Default)
- Agentforce Service Agent Builder
- Einstein Prompt Templates
- Prompt Template Manager

### API Version Notes

- `GenAiPlanner`: Available in API versions 60–63
- `GenAiPlannerBundle`: Available in API version 64+
- `AiAuthoringBundle` (Agent Script): Available in API version 65+

([source](https://docs.gearset.com/en/articles/10406855-how-to-deploy-genai-metadata-types),
[source](https://developer.salesforce.com/docs/ai/agentforce/guide/agent-dx-metadata.html))

---

## Pricing

Salesforce has iterated on pricing significantly:

| Model                | Details                                                              |
|----------------------|----------------------------------------------------------------------|
| Original (2024)      | $2 per conversation (drew backlash for unpredictability)             |
| Flex Credits (May 2025) | $0.10 per action (20 Flex Credits each), $500 for 100,000 credits |
| Per-user licensing   | Available for employee-facing agents, including unlimited usage SKUs |
| Agentforce add-on    | ~$125/user/month on top of existing Cloud editions                  |

A Digital Wallet dashboard tracks consumption in real time.

([source](https://www.salesforce.com/eu/agentforce/pricing/))

---

## Real-World Results

| Company            | Use Case                    | Results                                                    |
|--------------------|-----------------------------|------------------------------------------------------------|
| 1-800Accountant    | Tax season chat support     | ~50% inquiries resolved autonomously, 1,000+ answers in 24h|
| Engine (travel)    | Customer support            | 30% inquiries auto-resolved, 15% handle time reduction     |
| Globoplay          | WhatsApp subscriptions      | +110% NPS, +22% sales, 109% response accuracy increase     |
| PepsiCo            | Field sales & B2B workflows | Unified customer profiles, real-time stock visibility       |
| UChicago Medicine  | Patient self-service        | Automated scheduling, refills, insurance queries            |
| Vivint             | Smart home support          | 24/7 autonomous device troubleshooting                     |

([source](https://salesforce.com/news/press-releases/2025/06/23/agentforce-3-announcement),
[source](https://cirra.ai/articles/salesforce-agentforce-3-ai-agents))

---

## Known Limitations & Criticisms

- **B2B fit**: Agentforce was built primarily for transactional B2C service. B2B sales teams
  report sub-20% adoption due to chat-based UX and missing complex sales methodology tracking
  (MEDDPICC, buying committees).
  ([source](https://www.oliv.ai/blog/agentforce-usecase))

- **Data quality dependency**: Agents are only as good as the data. Companies with fragmented
  or dirty CRM data see inconsistent agent behavior.

- **Pricing complexity**: Three distinct pricing models in 18 months confused customers. True
  TCO can be higher than expected when factoring in Data Cloud, training, and technical expertise.

- **Production maturity**: Less than 10% of customers with Agentforce have moved past
  proof-of-concept into production, per Cleveland Research. About half of the 12,000 "customers"
  were free trials or promotional deployments.
  ([source](https://vantagepoint.io/blog/sf/state-of-ai-agentforce-financial-services-2026))

- **Platform lock-in**: Heavy reliance on Salesforce's proprietary stack. MCP adoption helps,
  but the ecosystem is still Salesforce-centric.

- **Oversight gaps**: 67% of companies reportedly operate AI agents with insufficient oversight,
  leading to costly mistakes.

---

## Competitive Landscape

Agentforce competes with:

- Microsoft Dynamics Copilot / Azure AI Agents
- Google Vertex AI Agents
- Amazon Q / Bedrock Agents
- IBM Watson Orchestrate
- Independent platforms (Maisa AI, etc.)

Agentforce's differentiator is deep CRM integration — if you're already in the Salesforce
ecosystem, agents have native access to your customer data, workflows, and metadata. The Command
Center observability layer is also relatively unique. The MCP open standard bet is strategic — if
it gains broad adoption, Salesforce becomes the control plane for multi-vendor agent ecosystems.

---

## Sources

Content was rephrased for compliance with licensing restrictions.

- [Salesforce Engineering: Atlas Reasoning Engine](https://engineering.salesforce.com/inside-the-brain-of-agentforce-revealing-the-atlas-reasoning-engine/)
- [Salesforce Engineering: Agentforce 360 Stack](https://engineering.salesforce.com/how-agentforce-data-and-apps-turned-the-salesforce-stack-into-agentforce-360/)
- [Salesforce: Agentforce 3 Announcement](https://salesforce.com/news/press-releases/2025/06/23/agentforce-3-announcement)
- [Salesforce: Agentforce Guide](https://www.salesforce.com/agentforce/guide/)
- [Salesforce: Einstein & Agentforce Myths](https://www.salesforce.com/blog/debunking-myths-salesforce-einstein-and-agentforce/)
- [Salesforce Developer: Agent DX Metadata](https://developer.salesforce.com/docs/ai/agentforce/guide/agent-dx-metadata.html)
- [Salesforce Developer: Agent Script Blocks](https://developer.salesforce.com/docs/ai/agentforce/guide/ascript-blocks.html)
- [Salesforce Developer: Agent Script Recipes](https://developer.salesforce.com/sample-apps/agent-script-recipes/getting-started/hello-world-agent)
- [Salesforce Developer: Natural Language Instructions](https://developer.salesforce.com/blogs/2025/01/how-to-write-effective-natural-language-instructions-for-agentforce)
- [Salesforce Developer: MCP Support](https://developer.salesforce.com/blogs/2025/06/introducing-mcp-support-across-salesforce)
- [Cirra.ai: Agentforce 3 Report](https://cirra.ai/articles/salesforce-agentforce-3-ai-agents)
- [Sweep.io: Agentforce 360 Guide](https://www.sweep.io/blog/a-360-degree-guide-to-agentforce-360)
- [Ceptes: Product Name Changes](https://ceptes.com/blogs/salesforce-product-name-changes-announced-at-dreamforce-2025/)
- [Gearset: Deploying GenAi Metadata](https://docs.gearset.com/en/articles/10406855-how-to-deploy-genai-metadata-types)
- [Salesforce Pricing](https://www.salesforce.com/eu/agentforce/pricing/)
- [Oliv.ai: Agentforce Use Cases](https://www.oliv.ai/blog/agentforce-usecase)
- [Vantagepoint: Financial Services State of AI](https://vantagepoint.io/blog/sf/state-of-ai-agentforce-financial-services-2026)

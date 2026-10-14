# Atlas Reasoning Engine — Logical Architecture

> Sources: [Salesforce Engineering Blog](https://engineering.salesforce.com/inside-the-brain-of-agentforce-revealing-the-atlas-reasoning-engine/), [Salesforce Atlas Blog](https://www.salesforce.com/blog/atlas-reasoning-engine/), [Cirra AI Analysis](https://cirra.ai/articles/salesforce-atlas-ai-reasoning-engine)
> Content was rephrased for compliance with licensing restrictions.

## What Is Atlas?

Atlas is Salesforce's proprietary AI reasoning engine — the "brain" of every Agentforce agent. It uses "System 2" inference-time reasoning (deliberate, multi-step thinking) rather than simple pattern matching. It employs ReAct prompting, integrated vector search, and feedback loops to mimic human-like reasoning. Early pilots show 33% better accuracy than traditional RAG and 2x improvement in response relevance.

## Atlas Cognitive Flywheel (Core Reasoning Loop)

```
                         ┌─────────────────┐
                         │   USER INPUT     │
                         │  (query/event/   │
                         │   API trigger)   │
                         └────────┬────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   TOPIC CLASSIFICATION   │
                    │                          │
                    │  Semantic matching on     │
                    │  topic name + description │
                    │  (NOT instructions/       │
                    │   actions)                │
                    │                          │
                    │  No match → "off-topic"   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   PROMPT CONSTRUCTION    │
                    │                          │
                    │  Assembles:              │
                    │  • User message          │
                    │  • Topic instructions    │
                    │  • Available actions     │
                    │  • Conversation history  │
                    │    (last 6 turns)        │
                    │  • Context variables     │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   EINSTEIN TRUST LAYER   │◄──── Security boundary
                    │                          │
                    │  • Data masking (PII)    │
                    │  • Secure LLM Gateway    │
                    │  • Zero data retention   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   LLM DECISION-MAKING    │
                    │                          │
                    │  Evaluates all inputs     │
                    │  and chooses:             │
                    │  • Direct answer          │
                    │  • Execute an action      │
                    │  • Ask clarifying Q       │
                    │  • Decline (out of scope) │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   GROUNDING VALIDATION   │
                    │                          │
                    │  Checks response against: │
                    │  • Topic instructions     │
                    │  • Verified business data │
                    │  • Hallucination filters  │
                    │  • Guardrail boundaries   │
                    │                          │
                    │  FAIL → retry loop ──────┼──┐
                    │  PASS → deliver response │  │
                    └────────────┬─────────────┘  │
                                 │                 │
                        ┌────────┘                 │
                        │                          │
                        ▼                          │
              ┌──────────────────┐                 │
              │  ACTION EXECUTION │                 │
              │  (if needed)      │                 │
              │                   │                 │
              │  Flow / Apex /    │                 │
              │  API / Prompt     │                 │
              │  Template         │                 │
              └────────┬─────────┘                 │
                       │                            │
                       ▼                            │
              ┌──────────────────┐                 │
              │  RESULT RETURNED  │                 │
              │  TO CONTEXT       ├─────────────────┘
              │                   │   (loop back if more
              │  May trigger      │    steps needed)
              │  another cycle    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  RESPONSE TO USER │
              │                   │
              │  • Data demasking │
              │  • Toxicity check │
              │  • Audit trail    │
              └──────────────────┘
```

## Atlas Agent Internal Components

Each Atlas agent is composed of three core internal components:

```
┌─────────────────────────────────────────────────────────────┐
│                    ATLAS AGENT INTERNALS                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                      STATE                           │    │
│  │                                                      │    │
│  │  Short-term memory: current conversation context     │    │
│  │  Long-term memory: past interactions, user data      │    │
│  │  Context variables: auto-populated (logged-in user)  │    │
│  │  Custom variables: flexible data containers          │    │
│  │                                                      │    │
│  │  Session ID tracks all interactions                  │    │
│  │  Memory persists across the full session lifecycle   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                      FLOW                            │    │
│  │                                                      │    │
│  │  Logical framework guiding the agent's actions       │    │
│  │  Determines next steps in a workflow                 │    │
│  │  Ensures coherent sequence of operations             │    │
│  │  Driven by topic classification + instructions       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   SIDE EFFECTS                       │    │
│  │                                                      │    │
│  │  Actions that impact the environment:                │    │
│  │  • Update CRM records                               │    │
│  │  • Create cases / opportunities                     │    │
│  │  • Trigger workflows                                │    │
│  │  • Call external APIs                               │    │
│  │  • Log interactions / audit trail                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Cooperative Agent Swarms (Multi-Agent Orchestration)

Atlas can orchestrate across multiple agents for complex queries:

```
                    ┌──────────────────────┐
                    │   USER QUERY         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  CONCIERGE           │
                    │  ORCHESTRATOR        │
                    │                      │
                    │  Routes to the right │
                    │  agent(s) based on   │
                    │  intent              │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │  AGENT A     │ │ AGENT B  │ │  AGENT C     │
     │  (Service)   │ │ (Sales)  │ │  (Specialist)│
     │              │ │          │ │              │
     │  Own topics  │ │ Own      │ │  Own topics  │
     │  Own actions │ │ topics   │ │  Own actions │
     │  Own state   │ │ Own      │ │  Own state   │
     │              │ │ actions  │ │              │
     └──────┬───────┘ └────┬─────┘ └──────┬───────┘
            │              │              │
            └──────────────┼──────────────┘
                           │
                           ▼
                    ┌──────────────────────┐
                    │  AGGREGATED RESPONSE  │
                    │  (Multiple POVs       │
                    │   combined)           │
                    └──────────────────────┘
```

## Scalability Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              ATLAS DISTRIBUTED ARCHITECTURE                  │
│                                                              │
│  Design: Asynchronous, event-driven, graph-based workflows  │
│  Pattern: Publish-subscribe (decoupled components)          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Function │  │ Function │  │ Function │  │ Function │   │
│  │ Node A   │  │ Node B   │  │ Node C   │  │ Node D   │   │
│  │          │  │          │  │          │  │          │   │
│  │ Strongly │  │ Strongly │  │ Strongly │  │ Strongly │   │
│  │ typed    │  │ typed    │  │ typed    │  │ typed    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│       └──────────────┴──────────────┴──────────────┘         │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              │  EVENT BUS            │                       │
│              │  (Pub/Sub)            │                       │
│              └───────────────────────┘                       │
│                                                              │
│  • Nodes operate independently but coherently               │
│  • Concurrent parallel execution across nodes               │
│  • Dynamic scaling without code changes                     │
│  • Geographically distributed across data centers           │
│  • Runs on Hyperforce (auth, container mgmt, compliance)    │
└─────────────────────────────────────────────────────────────┘
```

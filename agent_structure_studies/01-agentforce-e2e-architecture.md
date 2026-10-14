# Agentforce End-to-End Architecture

> Sources: [Salesforce Engineering Blog](https://engineering.salesforce.com/inside-the-brain-of-agentforce-revealing-the-atlas-reasoning-engine/), [Salesforce Agentforce Guide](https://www.salesforce.com/agentforce/guide/), [Pacific Data Integrators](https://www.pacificdataintegrators.com/blogs/blog/agentforce-enterprise-architecture-last-mile)
> Content was rephrased for compliance with licensing restrictions.

## Three-System Enterprise Architecture

The production Agentforce stack is built on three interconnected systems:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENTFORCE 360 PLATFORM                              │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────┐  │
│  │  SYSTEM OF CONTEXT │  │  SYSTEM OF WORK   │  │  SYSTEM OF AGENCY      │  │
│  │  (Data 360)        │  │  (Customer 360)   │  │  (Agentforce)          │  │
│  │                    │  │                   │  │                        │  │
│  │  • Unified         │  │  • Sales Cloud    │  │  • Agent Builder       │  │
│  │    Customer        │  │  • Service Cloud  │  │  • Atlas Reasoning     │  │
│  │    Profiles        │  │  • Marketing      │  │    Engine              │  │
│  │  • Zero-Copy       │  │    Cloud          │  │  • Topics/Actions/     │  │
│  │    Data Access     │  │  • Commerce       │  │    Instructions        │  │
│  │  • Real-Time       │  │    Cloud          │  │  • Einstein Trust      │  │
│  │    Data Engine     │  │  • Platform        │  │    Layer               │  │
│  │  • External        │  │    Workflows      │  │  • Guardrails &        │  │
│  │    System Data     │  │  • MuleSoft       │  │    Governance          │  │
│  │  • Vector Search   │  │    Integrations   │  │  • Deployment          │  │
│  │  • Data Graphs     │  │                   │  │    Channels            │  │
│  └────────┬───────────┘  └────────┬──────────┘  └───────────┬────────────┘  │
│           │                       │                          │               │
│           └───────────────────────┼──────────────────────────┘               │
│                                   │                                          │
│                    ┌──────────────┴──────────────┐                           │
│                    │     HYPERFORCE PLATFORM      │                           │
│                    │  (Security, Auth, Compliance) │                           │
│                    └─────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## End-to-End Request Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────────────────────────────┐
│  USER    │     │  CHANNEL     │     │         AGENTFORCE RUNTIME           │
│          │     │              │     │                                      │
│ Customer ├────►│ • Web Chat   ├────►│  1. Message Reception                │
│ Employee │     │ • Slack      │     │     │                                │
│ Partner  │     │ • Mobile     │     │  2. Topic Classification             │
│          │     │ • Messaging  │     │     │  (semantic matching)           │
│          │     │ • Voice      │     │  3. Instruction + Context Assembly   │
│          │     │ • API        │     │     │  (last 6 turns + actions)      │
└──────────┘     └──────────────┘     │  4. LLM Processing                  │
                                      │     │  (via Einstein Trust Layer)    │
                                      │  5. Action Execution                │
                                      │     │  (Flow/Apex/API/Prompt)       │
                                      │  6. Grounding Validation            │
                                      │     │  (accuracy + guardrails)      │
                                      │  7. Response Delivery               │
                                      └──────────────────────────────────────┘
                                                       │
                                      ┌────────────────┼────────────────┐
                                      │                │                │
                                      ▼                ▼                ▼
                               ┌───────────┐  ┌──────────────┐  ┌───────────┐
                               │ CRM Data  │  │ Data 360     │  │ External  │
                               │ (Records, │  │ (Profiles,   │  │ Systems   │
                               │  Cases,   │  │  Segments,   │  │ (APIs,    │
                               │  Opps)    │  │  Insights)   │  │  MuleSoft)│
                               └───────────┘  └──────────────┘  └───────────┘
```

## Agent Composition Model

Every Agentforce agent is defined by five key attributes:

```
                    ┌─────────────────────────┐
                    │      AGENTFORCE AGENT    │
                    └────────────┬────────────┘
                                 │
          ┌──────────┬───────────┼───────────┬──────────┐
          ▼          ▼           ▼           ▼          ▼
    ┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐
    │   ROLE   │ │  DATA  │ │ ACTIONS │ │GUARDRAILS│ │ CHANNEL │
    │          │ │        │ │         │ │          │ │         │
    │ Defines  │ │ What   │ │ What    │ │ What the │ │ Where   │
    │ the job  │ │ the    │ │ the     │ │ agent    │ │ the     │
    │ or       │ │ agent  │ │ agent   │ │ CANNOT   │ │ agent   │
    │ purpose  │ │ can    │ │ can DO  │ │ do       │ │ operates│
    │          │ │ ACCESS │ │         │ │          │ │         │
    └──────────┘ └────────┘ └─────────┘ └──────────┘ └─────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌──────────┐ ┌────────┐ ┌──────────┐
              │  TOPICS  │ │INSTRUCT│ │ ACTION   │
              │          │ │-IONS   │ │ TYPES    │
              │ Group    │ │        │ │          │
              │ requests │ │ Guide  │ │ • Flow   │
              │ into     │ │ convo  │ │ • Apex   │
              │ categories│ │ flow  │ │ • API    │
              │ (10-15   │ │ within │ │ • Prompt │
              │  max)    │ │ topics │ │ (8-10    │
              └──────────┘ └────────┘ │  per     │
                                      │  topic)  │
                                      └──────────┘
```

## Metadata Architecture (DevOps View)

```
┌─────────────────────────────────────────────────────────┐
│              AGENTFORCE METADATA STACK                    │
│              (API Version 60+)                            │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  GenAiPlanner / GenAiPlannerDefinition           │    │
│  │  (Reasoning service — task decomposition)        │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                                │
│  ┌──────────────────────┴──────────────────────────┐    │
│  │  GenAiPlugin (Topics + Instructions)             │    │
│  │  (What the agent understands and how it responds)│    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                                │
│  ┌──────────────────────┴──────────────────────────┐    │
│  │  GenAiFunction / GenAiFunctionDefinition         │    │
│  │  (Actions available to the agent)                │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                                │
│  ┌──────────────────────┴──────────────────────────┐    │
│  │  GenAiPromptTemplate                             │    │
│  │  (Reusable prompt templates with merge fields)   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  Deployment: Metadata API / Tooling API / SFDX / DevOps │
└─────────────────────────────────────────────────────────┘
```

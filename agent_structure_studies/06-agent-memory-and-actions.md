# Agent Memory, Actions & Function Calling — Logical Diagrams

> Sources: [Nectar Innovations](https://nectarinnovations.com/blog/inside-the-agent-how-salesforce-agentforce-works-under-the-hood), [Salesforce Agentforce Guide](https://www.salesforce.com/agentforce/guide/), [SFDC Developers](https://sfdcdevelopers.com/2026/02/20/architecting-agentforce-custom-actions-apex-metadata/)
> Content was rephrased for compliance with licensing restrictions.

## Agent Memory Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENTFORCE MEMORY SYSTEM                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                    SESSION MEMORY                              │     │
│  │                    (Unique Session ID)                         │     │
│  │                                                               │     │
│  │  ┌─────────────────────┐  ┌─────────────────────────────┐   │     │
│  │  │  CONTEXT VARIABLES  │  │  CUSTOM VARIABLES           │   │     │
│  │  │  (Auto-populated)   │  │  (Flexible containers)      │   │     │
│  │  │                     │  │                              │   │     │
│  │  │  • Logged-in user   │  │  • Store action outputs     │   │     │
│  │  │    identity         │  │  • Pass data between        │   │     │
│  │  │  • User permissions │  │    actions                  │   │     │
│  │  │  • Account details  │  │  • Can be inputs or         │   │     │
│  │  │  • No extra queries │  │    outputs for future       │   │     │
│  │  │    needed           │  │    actions                  │   │     │
│  │  │                     │  │  • No preset mappings       │   │     │
│  │  └─────────────────────┘  └─────────────────────────────┘   │     │
│  │                                                               │     │
│  │  Session Lifecycle:                                           │     │
│  │  1. Session created → memory ID assigned                     │     │
│  │  2. Memory loaded when session reused                        │     │
│  │  3. Variables updated continuously during conversation       │     │
│  │  4. Session summary generated on completion                  │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                 CONVERSATION HISTORY                           │     │
│  │                                                               │     │
│  │  Last 6 turns retained in prompt context                     │     │
│  │                                                               │     │
│  │  Turn 1: User → "What's my account balance?"                 │     │
│  │  Turn 2: Agent → "Your balance is $X. Need anything else?"   │     │
│  │  Turn 3: User → "Transfer $500 to savings"                   │     │
│  │  Turn 4: Agent → "Confirming transfer of $500..."            │     │
│  │  Turn 5: User → "Yes, confirm"                               │     │
│  │  Turn 6: Agent → "Transfer complete. Reference #12345"       │     │
│  └───────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Action Types & Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENTFORCE ACTION TYPES                               │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  STANDARD ACTIONS │  │  CUSTOM ACTIONS  │  │  AGENT SCRIPT    │     │
│  │  (Pre-configured) │  │  (You build)     │  │  (Beta - v64+)   │     │
│  │                   │  │                  │  │                  │     │
│  │  • Find records   │  │  • Flow Actions  │  │  YAML-like       │     │
│  │    by name        │  │    (Autolaunched │  │  deterministic    │     │
│  │  • Query data     │  │     Flows)       │  │  logic for       │     │
│  │  • Summarize      │  │                  │  │  controlling     │     │
│  │    records        │  │  • Apex Actions  │  │  agent           │     │
│  │                   │  │    (Invocable    │  │  transitions     │     │
│  │  No setup needed  │  │     Methods)     │  │                  │     │
│  │                   │  │                  │  │                  │     │
│  │                   │  │  • API Actions   │  │                  │     │
│  │                   │  │    (REST/MuleSoft│  │                  │     │
│  │                   │  │     external)    │  │                  │     │
│  │                   │  │                  │  │                  │     │
│  │                   │  │  • Prompt        │  │                  │     │
│  │                   │  │    Template      │  │                  │     │
│  │                   │  │    Actions       │  │                  │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Function-Calling Orchestration

```
┌─────────────────────────────────────────────────────────────────────────┐
│              FUNCTION-CALLING FLOW (Runtime)                             │
│                                                                         │
│  ┌──────────────┐                                                      │
│  │  User says:  │                                                      │
│  │  "Show my    │                                                      │
│  │   portfolio" │                                                      │
│  └──────┬───────┘                                                      │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  1. LLM ANALYZES INTENT                                  │          │
│  │                                                          │          │
│  │  Input: user message + topic instructions + actions      │          │
│  │  Output: structured function call                        │          │
│  │                                                          │          │
│  │  {                                                       │          │
│  │    "function": "DC_PortfolioReviewAction",               │          │
│  │    "arguments": {                                        │          │
│  │      "clientId": "001xx000003DGbY"                       │          │
│  │    }                                                     │          │
│  │  }                                                       │          │
│  └──────────────────────────┬───────────────────────────────┘          │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  2. ORCHESTRATION LAYER INTERCEPTS                       │          │
│  │                                                          │          │
│  │  • Validates function name against available actions     │          │
│  │  • Checks permissions (user has access?)                 │          │
│  │  • Validates arguments against action input schema       │          │
│  │  • Applies conditional filters                           │          │
│  └──────────────────────────┬───────────────────────────────┘          │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  3. ACTION EXECUTION                                     │          │
│  │                                                          │          │
│  │  Apex class invoked with proper security context:        │          │
│  │                                                          │          │
│  │  @InvocableMethod                                        │          │
│  │  public static List<Result> getPortfolio(                │          │
│  │      List<Request> requests) {                           │          │
│  │    // Query financial accounts                           │          │
│  │    // Calculate allocations                              │          │
│  │    // Return structured result                           │          │
│  │  }                                                       │          │
│  └──────────────────────────┬───────────────────────────────┘          │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  4. RESULT RETURNED TO CONTEXT                           │          │
│  │                                                          │
│  │  • Action output stored in custom variable              │          │
│  │  • Result added to conversation context                 │          │
│  │  • LLM generates natural language response              │          │
│  │  • May trigger another action cycle if needed           │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Conditional Filtering Logic

```
┌─────────────────────────────────────────────────────────────────────────┐
│              CONDITIONAL FILTERS (Topic & Action Gating)                 │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  TOPIC FILTERS                                               │      │
│  │  (Control which topics are visible)                          │      │
│  │                                                              │      │
│  │  Example: "Account Management" topic                         │      │
│  │  Filter: authenticationStatus = 'verified'                   │      │
│  │                                                              │      │
│  │  ┌──────────┐     ┌──────────────┐     ┌──────────────┐    │      │
│  │  │ User NOT │     │ Topic NOT    │     │ Agent says:  │    │      │
│  │  │ verified │────►│ available    │────►│ "Please      │    │      │
│  │  └──────────┘     └──────────────┘     │  verify your │    │      │
│  │                                         │  identity"   │    │      │
│  │  ┌──────────┐     ┌──────────────┐     └──────────────┘    │      │
│  │  │ User IS  │     │ Topic IS     │                          │      │
│  │  │ verified │────►│ available    │────► Normal processing   │      │
│  │  └──────────┘     └──────────────┘                          │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  ACTION FILTERS                                              │      │
│  │  (Control action sequencing)                                 │      │
│  │                                                              │      │
│  │  Example: "Process Refund" action                            │      │
│  │  Filter: orderNumber != null                                 │      │
│  │                                                              │      │
│  │  Step 1: User asks for refund                                │      │
│  │  Step 2: Agent runs "Lookup Order" → sets orderNumber var    │      │
│  │  Step 3: "Process Refund" action now unlocked                │      │
│  │  Step 4: Agent can execute refund with proper context        │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                         │
│  KEY DIFFERENCE:                                                        │
│  • Instructions = guide decisions WITHIN available options              │
│  • Filters = decide WHICH options appear in the first place            │
└─────────────────────────────────────────────────────────────────────────┘
```

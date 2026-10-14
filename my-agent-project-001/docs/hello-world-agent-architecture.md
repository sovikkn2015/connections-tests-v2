# Hello World Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HELLO WORLD AGENT                               │
│                                                                     │
│  Bot: Hello_World_Agent (EinsteinServiceAgent)                      │
│  Planner: Hello_World_Agent_v1                                      │
│  Apex Action: HelloAction.cls                                       │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    TOPIC SELECTOR                              │  │
│  │  "Select the tool that best matches the user's message"       │  │
│  └──────┬──────────┬──────────────┬──────────────┬───────────────┘  │
│         │          │              │              │                   │
│         ▼          ▼              ▼              ▼                   │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐             │
│  │ GREETING  │ │ESCALATION│ │OFF TOPIC │ │ AMBIGUOUS │             │
│  │           │ │          │ │          │ │ QUESTION  │             │
│  │ Greet the │ │ Transfer │ │ Redirect │ │ Ask user  │             │
│  │ user,     │ │ to live  │ │ politely │ │ to be     │             │
│  │ use name  │ │ human    │ │ back to  │ │ more      │             │
│  │ if given  │ │ agent    │ │ topics   │ │ specific  │             │
│  └─────┬─────┘ └────┬─────┘ └──────────┘ └───────────┘             │
│        │             │                                              │
│        ▼             ▼                                              │
│  ┌───────────┐ ┌──────────────┐                                     │
│  │get_greeting│ │escalate_to_  │                                     │
│  │           │ │human         │                                     │
│  │ ACTION    │ │ ACTION       │                                     │
│  │           │ │              │                                     │
│  │ target:   │ │ target:      │                                     │
│  │ apex://   │ │ @utils.      │                                     │
│  │ HelloActi │ │ escalate     │                                     │
│  │ on        │ │              │                                     │
│  │           │ │              │                                     │
│  │ in:       │ │              │                                     │
│  │  userName │ │              │                                     │
│  │ out:      │ │              │                                     │
│  │  greeting │ │              │                                     │
│  │  Message  │ │              │                                     │
│  └───────────┘ └──────────────┘                                     │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                     │
│  TEST RESULTS (Latest Run)                                          │
│                                                                     │
│  "Hello, my name is Sam"              Topic ✔  Action ✘  Outcome ✔  │
│   → "Hello, Sam! How can I help you today?"                         │
│                                                                     │
│  "I want to talk to a real person"    Topic ✔  Action ✘  Outcome ✔  │
│   → "I will connect you to a real person now..."                    │
│                                                                     │
│  Topic Pass: 100%  |  Action Pass: 0%  |  Outcome Pass: 100%       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

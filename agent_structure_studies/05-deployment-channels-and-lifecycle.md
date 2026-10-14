# Agent Deployment Channels & Lifecycle Management

> Sources: [Salesforce Agentforce Guide](https://www.salesforce.com/agentforce/guide/), [Slack Agentforce Blog](https://slack.com/blog/news/limitless-workforce-with-agentforce-in-slack), [Agentforce Developer Guide](https://developer.salesforce.com/docs/einstein/genai/guide/trust.html)
> Content was rephrased for compliance with licensing restrictions.

## Multi-Channel Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENTFORCE DEPLOYMENT CHANNELS                        │
│                                                                         │
│                         ┌──────────────────┐                            │
│                         │  AGENTFORCE      │                            │
│                         │  AGENT           │                            │
│                         │  (Single Build)  │                            │
│                         └────────┬─────────┘                            │
│                                  │                                      │
│         ┌────────┬───────┬───────┼───────┬────────┬────────┐           │
│         ▼        ▼       ▼       ▼       ▼        ▼        ▼           │
│    ┌─────────┐┌──────┐┌──────┐┌──────┐┌───────┐┌──────┐┌───────┐     │
│    │  WEB    ││SLACK ││MOBILE││MESSAG││ VOICE ││ API  ││EXPERI-│     │
│    │  CHAT   ││      ││ APP  ││-ING  ││       ││      ││-ENCE  │     │
│    │         ││      ││      ││      ││       ││      ││CLOUD  │     │
│    │Embedded ││@ment-││SF    ││SMS   ││Phone  ││REST  ││Sites  │     │
│    │Service  ││ion in││Mobile││What- ││IVR    ││Graph-││Portal │     │
│    │Chat     ││DMs & ││App   ││sApp  ││       ││QL   ││       │     │
│    │Widget   ││Chan- ││      ││FB    ││       ││      ││       │     │
│    │         ││nels  ││      ││Msg   ││       ││      ││       │     │
│    └─────────┘└──────┘└──────┘└──────┘└───────┘└──────┘└───────┘     │
│                                                                         │
│    Customer-Facing          Employee-Facing         Developer/          │
│    Channels                 Channels                Integration         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Slack Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  SLACK + AGENTFORCE                            │
│                                                               │
│  ┌──────────────┐         ┌──────────────────────────────┐   │
│  │  SLACK       │         │  SALESFORCE ORG               │   │
│  │  WORKSPACE   │         │                               │   │
│  │              │         │  ┌──────────────────────┐    │   │
│  │  User types  │  API    │  │  Agentforce Builder   │    │   │
│  │  @AgentName  ├────────►│  │                       │    │   │
│  │  in channel  │         │  │  Agent processes      │    │   │
│  │  or DM       │         │  │  request via Atlas    │    │   │
│  │              │◄────────┤  │  Reasoning Engine     │    │   │
│  │  Agent       │  Reply  │  │                       │    │   │
│  │  responds    │         │  │  Accesses CRM data,   │    │   │
│  │  in thread   │         │  │  Data 360, actions    │    │   │
│  │              │         │  └──────────────────────┘    │   │
│  │  Can create  │         │                               │   │
│  │  canvases,   │         │  Connection approved by       │   │
│  │  update      │         │  Slack admin + SF admin       │   │
│  │  records     │         │                               │   │
│  └──────────────┘         └──────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Agent Lifecycle Management

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT LIFECYCLE (End-to-End)                          │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  PLAN    │  │  BUILD   │  │  TEST    │  │  DEPLOY  │  │ MONITOR │ │
│  │          │  │          │  │          │  │          │  │ & TUNE  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │              │      │
│       ▼              ▼              ▼              ▼              ▼      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │• Identify│  │• Agent   │  │• Agent   │  │• Channel │  │• Perf   │ │
│  │  use case│  │  Builder │  │  Eval    │  │  config  │  │  metrics│ │
│  │          │  │          │  │  (AI     │  │          │  │         │ │
│  │• Define  │  │• Topics  │  │  Evalua- │  │• Phased  │  │• Accur- │ │
│  │  success │  │  & inst- │  │  tion    │  │  rollout │  │  acy    │ │
│  │  metrics │  │  ructions│  │  Defini- │  │          │  │  scores │ │
│  │          │  │          │  │  tions)  │  │• Permis- │  │         │ │
│  │• Map     │  │• Actions │  │          │  │  sion    │  │• Escal- │ │
│  │  data    │  │  (Flow,  │  │• Test    │  │  sets    │  │  ation  │ │
│  │  sources │  │  Apex,   │  │  cases   │  │          │  │  rates  │ │
│  │          │  │  API)    │  │          │  │• Guard-  │  │         │ │
│  │• Stake-  │  │          │  │• LLM-as- │  │  rails   │  │• Drift  │ │
│  │  holder  │  │• Guard-  │  │  Judge   │  │  final-  │  │  detect-│ │
│  │  align   │  │  rails   │  │  scoring │  │  ized    │  │  ion    │ │
│  │          │  │          │  │          │  │          │  │         │ │
│  │• 2-6 wks │  │• Prompt  │  │• E2E    │  │• Go-live │  │• Contin-│ │
│  │  typical │  │  Builder │  │  traces  │  │          │  │  uous   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                                         │
│  ◄─────────────────── 2-6 weeks typical ──────────────────────────►    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## DevOps & CI/CD for Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT DEVOPS PIPELINE                                 │
│                                                                         │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐      │
│  │  SOURCE  │     │  BUILD   │     │  STAGING │     │  PROD    │      │
│  │  CONTROL │────►│  & TEST  │────►│  ORG     │────►│  ORG     │      │
│  │          │     │          │     │          │     │          │      │
│  │  Git repo│     │  SFDX    │     │  Deploy  │     │  Deploy  │      │
│  │  with:   │     │  push    │     │  & run   │     │  with    │      │
│  │          │     │          │     │  AI Eval │     │  phased  │      │
│  │  • .agent│     │  Metadata│     │  tests   │     │  rollout │      │
│  │  • .cls  │     │  API     │     │          │     │          │      │
│  │  • .xml  │     │  deploy  │     │  Gate:   │     │  Monitor │      │
│  │  • .yaml │     │          │     │  pass/   │     │  & tune  │      │
│  │          │     │          │     │  fail    │     │          │      │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘      │
│                                                                         │
│  Metadata types deployed:                                               │
│  • GenAiPlannerBundle (reasoning config)                                │
│  • GenAiPlugin (topics + instructions)                                  │
│  • GenAiFunction (actions)                                              │
│  • GenAiPromptTemplate (prompt templates)                               │
│  • BotVersion (agent version)                                           │
│  • AiEvaluationDefinition (test specs)                                  │
│  • AiAuthoringBundle (agent definition)                                 │
│  • PermissionSet (access control)                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Human Handoff Pattern

```
┌─────────────────────────────────────────────────────────────┐
│              HUMAN-IN-THE-LOOP ESCALATION                    │
│                                                              │
│  ┌──────────┐                                               │
│  │  Agent   │                                               │
│  │  handles │                                               │
│  │  request │                                               │
│  └────┬─────┘                                               │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────────────────────┐                   │
│  │  CONFIDENCE CHECK                    │                   │
│  │                                      │                   │
│  │  Is confidence above threshold?      │                   │
│  │  Is this a high-risk action?         │                   │
│  │  Does guardrail require human?       │                   │
│  └──────────┬──────────────┬────────────┘                   │
│             │              │                                 │
│        HIGH CONF      LOW CONF / HIGH RISK                  │
│             │              │                                 │
│             ▼              ▼                                 │
│  ┌──────────────┐  ┌──────────────────┐                    │
│  │  AUTONOMOUS  │  │  ESCALATE TO     │                    │
│  │  RESOLUTION  │  │  HUMAN AGENT     │                    │
│  │              │  │                  │                    │
│  │  Agent       │  │  Full context    │                    │
│  │  completes   │  │  transferred:    │                    │
│  │  action &    │  │  • Conversation  │                    │
│  │  responds    │  │  • Actions taken │                    │
│  │              │  │  • Customer data │                    │
│  │              │  │  • Reason for    │                    │
│  │              │  │    escalation    │                    │
│  └──────────────┘  └──────────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

# Einstein Trust Layer — Security Architecture

> Sources: [Salesforce FAQs](https://salesforcefaqs.com/einstein-trust-layer-in-salesforce-agentforce), [Trailhead Trust Layer Module](https://trailhead.salesforce.com/content/learn/modules/the-einstein-trust-layer/), [Nebula Consulting](https://nebulaconsulting.co.uk/insights/why-the-einstein-trust-layer-is-a-key-part-of-agentforce/)
> Content was rephrased for compliance with licensing restrictions.

## What Is the Einstein Trust Layer?

The Einstein Trust Layer is Salesforce's secure AI architecture that protects company and customer data during all generative AI interactions. It acts as a guardian managing the flow of information between Salesforce, the agent, and external LLM providers.

Key principles:
- Zero data retention with LLM providers (data is forgotten after response generation)
- PII masking before data leaves the Salesforce trust boundary
- Toxicity detection on all responses
- Full audit trail of every AI interaction

## End-to-End Trust Layer Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SALESFORCE TRUST BOUNDARY                            │
│                                                                          │
│  ┌──────────┐    ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  USER    │    │  1. PROMPT &     │    │  2. DYNAMIC GROUNDING    │   │
│  │  REQUEST │───►│  SECURE DATA     │───►│                          │   │
│  │          │    │  RETRIEVAL       │    │  Salesforce data added   │   │
│  └──────────┘    │                  │    │  to prompt for           │   │
│                  │  CRM data pulled │    │  personalized response   │   │
│                  │  securely        │    │                          │   │
│                  └──────────────────┘    └────────────┬─────────────┘   │
│                                                       │                  │
│                                                       ▼                  │
│                                          ┌──────────────────────────┐   │
│                                          │  3. DATA MASKING         │   │
│                                          │                          │   │
│                                          │  PII detected & masked:  │   │
│                                          │  • Email addresses       │   │
│                                          │  • Phone numbers         │   │
│                                          │  • Names                 │   │
│                                          │  • Account numbers       │   │
│                                          │                          │   │
│                                          │  [email] → [MASKED_001] │   │
│                                          └────────────┬─────────────┘   │
│                                                       │                  │
│                                                       ▼                  │
│                                          ┌──────────────────────────┐   │
│                                          │  4. SECURE LLM GATEWAY   │   │
│                                          │                          │   │
│                                          │  Encrypted transport     │   │
│                                          │  to external LLM         │   │
│                                          └────────────┬─────────────┘   │
│                                                       │                  │
└───────────────────────────────────────────────────────┼──────────────────┘
                                                        │
                              ┌──────────────────────────┘
                              ▼
               ┌──────────────────────────┐
               │  EXTERNAL LLM PROVIDERS  │
               │                          │
               │  • OpenAI                │
               │  • Anthropic             │
               │  • Other providers       │
               │                          │
               │  ┌────────────────────┐  │
               │  │ ZERO DATA          │  │
               │  │ RETENTION POLICY   │  │
               │  │                    │  │
               │  │ Data is NOT stored │  │
               │  │ Data is NOT used   │  │
               │  │ for training       │  │
               │  └────────────────────┘  │
               └────────────┬─────────────┘
                            │
                            ▼ (response returned)
┌───────────────────────────────────────────────────────────────────────────┐
│                     SALESFORCE TRUST BOUNDARY (Return Path)               │
│                                                                           │
│  ┌──────────────────────────┐    ┌──────────────────────────┐            │
│  │  5. DATA DEMASKING       │    │  6. TOXICITY DETECTION   │            │
│  │                          │    │                          │            │
│  │  [MASKED_001] → [email] │───►│  Reviews response for:   │            │
│  │                          │    │  • Harmful content       │            │
│  │  Original values         │    │  • Inappropriate language│            │
│  │  restored                │    │  • Policy violations     │            │
│  └──────────────────────────┘    └────────────┬─────────────┘            │
│                                                │                          │
│                                                ▼                          │
│                                   ┌──────────────────────────┐           │
│                                   │  7. AUDIT TRAIL          │           │
│                                   │                          │           │
│                                   │  Every interaction       │           │
│                                   │  logged for compliance:  │           │
│                                   │  • Prompt sent           │           │
│                                   │  • Response received     │           │
│                                   │  • Actions taken         │           │
│                                   │  • Masking applied       │           │
│                                   │  • Toxicity scores       │           │
│                                   └────────────┬─────────────┘           │
│                                                │                          │
│                                                ▼                          │
│                                   ┌──────────────────────────┐           │
│                                   │  RESPONSE TO USER        │           │
│                                   └──────────────────────────┘           │
└───────────────────────────────────────────────────────────────────────────┘
```

## Trust Layer in the Agent Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Agent Builder          Atlas Reasoning         Trust Layer     │
│   (Design Time)          Engine (Runtime)        (Every Call)    │
│                                                                  │
│   ┌──────────┐          ┌──────────────┐      ┌──────────────┐ │
│   │ Define   │          │ Classify     │      │ Mask PII     │ │
│   │ Topics   │─────────►│ Topic        │─────►│              │ │
│   │          │          │              │      │ Secure       │ │
│   │ Write    │          │ Assemble     │      │ Gateway      │ │
│   │ Instruct-│          │ Prompt       │      │              │ │
│   │ ions     │          │              │      │ Zero         │ │
│   │          │          │ Call LLM     │◄────►│ Retention    │ │
│   │ Configure│          │              │      │              │ │
│   │ Actions  │          │ Validate     │      │ Demask       │ │
│   │          │          │ Grounding    │      │              │ │
│   │ Set      │          │              │      │ Toxicity     │ │
│   │ Guard-   │          │ Execute      │      │ Check        │ │
│   │ rails    │          │ Action       │      │              │ │
│   │          │          │              │      │ Audit Log    │ │
│   └──────────┘          └──────────────┘      └──────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Guardrails Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENTFORCE GUARDRAILS                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LAYER 1: TOPIC BOUNDARIES                          │    │
│  │  • Agent only responds within defined topics        │    │
│  │  • Off-topic queries get controlled fallback        │    │
│  │  • Conditional filters gate topic availability      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LAYER 2: ACTION RESTRICTIONS                       │    │
│  │  • Actions limited to 8-10 per topic                │    │
│  │  • Input instructions define when/how to trigger    │    │
│  │  • Conditional filters enforce sequencing           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LAYER 3: GROUNDING VALIDATION                      │    │
│  │  • Response checked against instructions            │    │
│  │  • Verified against business data                   │    │
│  │  • Hallucination detection                          │    │
│  │  • Retry loop on failure                            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LAYER 4: EINSTEIN TRUST LAYER                      │    │
│  │  • PII masking / demasking                          │    │
│  │  • Toxicity detection                               │    │
│  │  • Zero data retention                              │    │
│  │  • Audit trail                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LAYER 5: PLATFORM SECURITY (HYPERFORCE)            │    │
│  │  • Authentication & authorization                   │    │
│  │  • Container management                             │    │
│  │  • Compliance (SOC2, HIPAA, etc.)                   │    │
│  │  • Phased rollout controls                          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

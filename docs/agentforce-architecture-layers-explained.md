# Agentforce Architecture Layers — Explained

This document explains the different layers in the Agentforce Wealth Advisor architecture, what they are, why they exist, and how they map to LangChain and AWS equivalents.

---

## Layer-by-Layer Walkthrough (Top to Bottom)

### Deployment Channels (Purple)

How users reach the agent. Web Chat is the Experience Cloud portal. Slack and Mobile are additional channels. All three feed into the same agent — the user doesn't know or care which backend handles their query.

### Agentforce Platform (Blue)

The AI brain. The agent (WA P1to5 Advisor) receives natural language from any channel. The Atlas Reasoning Engine figures out what the user wants. The Topic Selector classifies the intent into one of 10 topics. Think of it like a smart receptionist — "you want portfolio info? let me route you to the right department." Escalation and Off-Topic are guardrails that handle "I want a human" and "what's the weather" without calling any data action.

### Apex Data Layer (Light Blue)

The hands that do the work. Each topic maps to an Apex class marked with `@InvocableMethod` so the agent can call it. These are the actual code that runs when the agent decides what to do. Phase 1 classes (ClientLookup, PortfolioReview, GoalPlanning, MeetingPrep) query client data. Phase 2 adds Rebalancing, Transactions, Compliance, Referrals. The gold MCP classes (MarketData, NewsSearch) call external APIs instead of Data Cloud. AuditLog (red) writes compliance records.

### Data Cloud DLM (Pink)

The unified data layer. Instead of querying CRM objects directly with SOQL (which is what project 002 does), project 004 queries Data Cloud's Data Lake Model tables using `ConnectApi.CdpQuery`. Data Cloud can unify data from multiple sources (CRM, external systems, data warehouses) into one queryable layer. The DLM tables are mirrors of the CRM objects, kept in sync automatically.

### External APIs (Gold)

Real-time external data. Market prices from Alpha Vantage, financial news from NewsAPI, web search from Tavily. These give the agent current information that doesn't exist in Salesforce.

### CRM Objects (Green)

The source of truth. The 8 custom objects (Client, Financial Account, Goal, Meeting, Transaction, Referral, etc.) hold the actual business data. The CRM Connector automatically syncs these into Data Cloud DLM tables. The Audit Log is CRM-only (not synced to Data Cloud) because it's a write destination, not a read source.

### Key Design Insight

The agent never touches the database directly. It goes Agent → Topic → Apex → Data Cloud/API → back up. Each layer has a single responsibility, and you can swap any layer without affecting the others.

---

## Comparison Table: Topics vs Apex vs DLM vs CRM

| | Topics | Apex Data Layer | Data Cloud DLM | CRM Objects |
|---|--------|----------------|----------------|-------------|
| What it is | Intent classifiers in the agent script | Apex classes with `@InvocableMethod` | Read-optimized data lake tables (`__dlm`) | Transactional custom objects (`__c`) |
| Purpose | Route user's question to the right action | Execute business logic, query data, format response | Unified query layer across multiple data sources | Store source of truth for business data |
| Analogy | Phone menu — except AI picks automatically | The specialist who looks up your account | Data warehouse mirroring production DB | Production database where the app writes |
| Who decides | The LLM (Atlas Reasoning Engine) | The agent calls the Apex class mapped to the selected topic | Apex code queries DLM via `CdpQuery` | Users/apps write here via UI, API, or DML |
| Query language | N/A (LLM classification) | Apex code | ANSI SQL (via ConnectApi) | SOQL |
| Optimized for | Intent classification speed | Code execution, business rules | Read-heavy analytics queries, cross-source joins | CRUD operations |
| Data direction | Input: user message → Output: topic name | Input: topic + params → Output: formatted string | Read-only (agent reads from here) | Read + Write (source of truth) |
| Count in project 004 | 10 topics | 11 Apex classes | 7 DLM tables | 8 custom objects |
| Example | `client_lookup` — triggers when user says "Tell me about Johnson" | `DC_ClientLookupAction` — takes "Johnson", queries DLM, returns "$2.8M AUM" | `WA_Client_c_Home__dlm` — 10 client records synced from CRM | `WA_Client__c` — actual client records advisors create |
| Can exist without others? | No — needs Apex actions to do anything | Yes — could query CRM directly (project 002) | No — needs CRM objects as source data | Yes — exists independently |
| LangChain equivalent | Router chain / `MultiPromptChain` / LangGraph conditional edges | `@tool` decorator / `BaseTool` subclasses | Vector store / Retriever (Pinecone, Chroma, FAISS) | PostgreSQL / MongoDB (source database) |
| AWS equivalent | Lex V2 intents / Bedrock Agent intent classification | Lambda functions invoked by Bedrock Agent | Redshift / Athena / Lake Formation | RDS / DynamoDB / Aurora |
| Why it exists | Without routing, the agent tries to answer everything with one generic prompt — bad accuracy | Without code, the agent can only talk — can't fetch real data | Without DLM, you query CRM directly (slower, can't join external data) | Without CRM objects, there's no data to query |

---

## DLM vs CRM: Why Both?

CRM is where data lives and gets written. DLM is where data gets read by the agent. They contain the same data (synced automatically), but DLM is optimized for the agent's query patterns while CRM is optimized for the app's CRUD operations.

- Project 002 skips DLM entirely and queries CRM directly via SOQL — simpler but less scalable.
- Project 003/004 add the DLM layer for production-grade data access.

The CRM Connector (dashed arrow in the diagram) handles the automatic sync. When an advisor creates a new client in Salesforce, it appears in Data Cloud within minutes.

---

## Data Flow: End to End

```
User types: "Tell me about the Johnson household"
    │
    ▼
Deployment Channel (Web Chat / Slack / Mobile)
    │
    ▼
Agent (WA P1to5 Advisor) — Atlas Reasoning Engine
    │
    ▼
Topic Selector → picks "client_lookup"
    │
    ▼
Apex: DC_ClientLookupAction.getClient360("Johnson")
    │
    ▼
Data Cloud: SELECT * FROM WA_Client_c_Home__dlm WHERE Name LIKE '%Johnson%'
    │
    ▼
Returns: Johnson Family, $2.8M AUM, Moderate risk, Sarah + Tom, 3 accounts
    │
    ▼
Agent formats response → sends back to user
```

---

## Architecture Diagrams

- Project 002 (CRM/SOQL): `my-agent-project-002-fsi-wealth_advisor_agent/docs/architecture-002-wa-crm.drawio`
- Project 003 (Data Cloud): `my-agent-project-003-fsi-wealth_advisor_agent-datacloud/docs/architecture-003-wa-datacloud.drawio`
- Project 004 (Full Phase 1-5): `my-agent-project-004-fsi-wealth_advisor_agent-phase1to5/docs/architecture-004-wa-phase1to5.drawio`

Open any `.drawio` file in [draw.io](https://app.diagrams.net) or VS Code with the draw.io extension.


---

## Agentforce Platform Options — Models, Tools, Data, Protocols, Architecture

### Models

| Option | Details |
|--------|---------|
| Salesforce Default | Managed mix of trusted models (currently GPT-4o), optimized by Salesforce for accuracy and trust |
| AWS-Hosted | Anthropic Claude Sonnet 4 on Amazon Bedrock (within Salesforce Trust Boundary) |
| OpenAI / Azure OpenAI | GPT-4o, GPT-4o Mini, GPT-4.1, GPT-4.1 Mini, GPT-5, GPT-5 Mini, GPT-5.1, GPT-5.2, O3, O4 Mini |
| Anthropic on Bedrock | Claude Haiku 4.5, Claude Sonnet 4, Claude Sonnet 4.5, Claude Opus 4.5 (all within SF Trust Boundary) |
| Google Vertex AI | Gemini 2.5 Flash, 2.5 Flash Lite, 2.5 Pro, 3 Flash, 3 Pro, 3.1 Pro |
| Amazon Nova | Nova Lite, Nova Pro (on Bedrock, within SF Trust Boundary) |
| NVIDIA | Nemotron 3 Nano 30B (Beta, on Bedrock) |
| BYOLLM (Bring Your Own) | Connect any model from Amazon Bedrock, Azure OpenAI, OpenAI, or Vertex AI using your own credentials. 30% fewer Einstein Requests consumed. |
| BYOLLM Open Connector | Connect ANY LLM (including custom/open-source models like IBM Granite, Databricks DBRX, self-hosted) via OpenAI-compatible API spec |

Source: [Salesforce Supported Models](https://developer.salesforce.com/docs/einstein/genai/guide/supported-models.html) (content rephrased for compliance)

### Tools / Action Types

| Action Type | How It Works | Best For |
|-------------|-------------|----------|
| Flow (Autolaunched) | Low-code/no-code. Build in Flow Builder, mark as agent action. | Simple CRUD, record creation, field updates |
| Apex (@InvocableMethod) | Pro-code. Write Apex classes with `@InvocableMethod` annotation. | Complex logic, Data Cloud queries, HTTP callouts, bulk operations |
| Prompt Template | Generative AI task. Define a template with merge fields grounded in CRM data. | Summarizing records, drafting emails, generating reports |
| External Services | Import an OpenAPI spec, Salesforce auto-generates Apex classes. | Calling external REST APIs without writing code |
| MuleSoft | Enterprise integration. Connect legacy systems, ERPs, databases at scale. | SAP, Oracle, Workday, on-prem systems |
| Standard/System Actions | Built-in: `@utils.escalate`, Knowledge search, record queries. | Escalation, knowledge grounding, basic CRM operations |

### Data Sources

| Source | Access Method | Use Case |
|--------|-------------|----------|
| CRM Objects (SOQL) | Direct SOQL queries from Apex | Simple, fast access to Salesforce data. Project 002 approach. |
| Data Cloud / Data 360 (CdpQuery) | `ConnectApi.CdpQuery.queryAnsiSqlV2()` via ANSI SQL | Unified data from CRM + external sources. Project 003/004 approach. |
| Knowledge Articles (RAG) | Einstein Knowledge Grounding on agent | Policy docs, FAQs, procedures |
| External APIs (HTTP Callout) | Apex `Http` class or Named Credentials | Market data, news feeds, third-party services |
| MCP Servers (external) | MCP protocol via AgentExchange | Any external tool/data source exposing an MCP server |
| Zero-Copy from Data Warehouses | Data Cloud connectors (Snowflake, BigQuery, Redshift) | Query warehouse data without copying into Salesforce |
| Calculated Insights | Data Cloud computed metrics | Pre-computed KPIs: churn risk, engagement scores |
| Vector Search (RAG) | Data Cloud vector database | Semantic search over unstructured content |

### Integration Protocols

| Protocol | Status | What It Does |
|----------|--------|-------------|
| MCP (Model Context Protocol) | GA in Agentforce 3 | Open standard (by Anthropic) for agents to discover and use external tools/data. Agentforce acts as both MCP client and MCP server. |
| A2A (Agent-to-Agent) | Coming soon | Google's protocol for agent-to-agent communication. |
| OpenAPI / External Services | GA | Import any REST API's OpenAPI spec, auto-generates callable actions. |
| Named Credentials | GA | Secure credential storage for external API authentication. |
| MuleSoft Anypoint | GA | Enterprise integration platform for connecting any system. |
| AgentExchange | GA | Marketplace for pre-built MCP servers, agent skills, and partner integrations. |
| Platform Events | GA | Real-time event-driven integration (publish/subscribe). |

### Agent Architecture Patterns

| Pattern | Description | When to Use |
|---------|-------------|-------------|
| Single Agent | One agent with multiple topics and actions. Atlas handles all routing. | Most use cases. Our WA P1to5 Advisor is this — 10 topics, 11 actions, one agent. |
| Multi-Agent (Orchestrator) | One manager agent delegates to specialized sub-agents. | Complex workflows where different domains need isolation. |
| Agent-to-Agent (MCP/A2A) | Independent agents communicate via MCP or A2A protocol. Can be cross-platform. | Cross-system orchestration: SF agent calls AWS agent. |
| Headless Agent (Agent API) | No UI. Agent invoked programmatically via REST API. | Backend automation, mobile SDK, custom UIs. |
| Agent from Flow/Apex | Trigger an agent from a Flow or Apex code as a sub-process. | Event-driven: "when a case is created, invoke the agent." |


---

## How to Select LLMs in Agentforce

Model selection happens at three levels:

### Level 1: Agent-Level Model (Reasoning Engine)

Controls which LLM the Atlas Reasoning Engine uses for topic classification, planning, and response generation. Set once per org — applies to ALL agents.

- Setup → Agentforce → Agents page → "Model Option" dropdown
- Two choices:
  - "Salesforce Default" — managed mix of trusted models (currently GPT-4o), optimized by Salesforce
  - "AWS-Hosted" — Anthropic Claude Sonnet 4 on Amazon Bedrock
- You cannot pick different reasoning models per agent — it's org-wide

### Level 2: Action-Level Model (Prompt Templates and Models API)

When an agent action uses a Prompt Template or calls the Models API from Apex, you can pick ANY model from the full catalog.

- Setup → Einstein Studio → Model Library — lists all available models
- In Prompt Builder: select the model when creating a template
- In Apex: specify the model API name — `ConnectApi.EinsteinLLM.generateChat(modelName, ...)`
- Each prompt template or API call can use a different model
- Full catalog: GPT-5, Claude Opus 4.5, Gemini 3 Pro, Nova Pro, BYOLLM models, etc.

### Level 3: BYOLLM Setup (Bring Your Own)

To add your own model:

1. Setup → Einstein Studio → Add Foundation Model
2. Pick provider: Amazon Bedrock, Azure OpenAI, OpenAI, or Vertex AI
3. Enter your credentials (API key, endpoint)
4. The model appears in the Model Library — usable in prompt templates and Models API
5. For completely custom models (self-hosted, open-source): use the BYOLLM Open Connector — host an OpenAI-compatible API endpoint and point Einstein Studio at it

### Summary

| Level | Scope | Choices | Where to Set |
|-------|-------|---------|-------------|
| Agent Reasoning | Org-wide (all agents) | 2 options: Salesforce Default or AWS-Hosted | Setup → Agentforce → Agents → Model Option |
| Action/Prompt | Per prompt template or API call | Full catalog (25+ models) + BYOLLM | Prompt Builder or Apex code |
| BYOLLM | Custom models | Any LLM via supported providers or Open Connector | Setup → Einstein Studio → Add Foundation Model |

Our project uses the Salesforce Default for reasoning — we never changed it. All 11 Apex actions use `@InvocableMethod` (not prompt templates), so they don't invoke the LLM directly — they run deterministic code that queries Data Cloud and formats the response.


---

## Connecting External Data (AWS, GCP, etc.) to Agentforce Agents

Six methods, from no-code to deep integration:

| Method | Data Stays Where | Latency | Code Required | Best For |
|--------|-----------------|---------|---------------|----------|
| 1. Zero-Copy (Data Cloud) | In your warehouse (S3, Redshift, BigQuery, Snowflake) | Low (federated query) | No code | Large datasets you don't want to copy into Salesforce |
| 2. Data Cloud Ingestion | Copied into Data Cloud | Minutes (batch sync) | No code | External data you want unified with CRM data |
| 3. Apex HTTP Callout | In your API (Lambda, Cloud Functions, any REST endpoint) | Real-time per request | Apex code | Real-time lookups, small payloads, API-first services |
| 4. External Services (OpenAPI) | In your API | Real-time per request | No code (import spec) | REST APIs with an OpenAPI/Swagger spec |
| 5. MuleSoft | Anywhere (databases, ERPs, queues, files) | Real-time or batch | MuleSoft flows | Enterprise systems, complex transformations, on-prem |
| 6. MCP Server | In your external system | Real-time per request | MCP server code | Any tool/data source you want agents to discover dynamically |

### 1. Zero-Copy (Data Cloud Connectors)

Your data stays in AWS S3, Redshift, Snowflake, or GCP BigQuery. Data Cloud creates virtual DMO tables that point to your warehouse. The agent queries these via CdpQuery just like any other DLM table, but the data never leaves your warehouse.

Setup: Data Cloud → Data Streams → New → select your cloud connector (Amazon S3, Redshift, Snowflake, BigQuery).

### 2. Data Cloud Ingestion

Data is physically copied from your external source into Data Cloud. Supports S3, GCS, Azure Blob, SFTP, or any streaming source. Good when you need the data unified with CRM records for identity resolution.

Setup: Data Cloud → Data Streams → New → Ingestion API or file-based connector.

### 3. Apex HTTP Callout

Write an Apex class that calls your external API directly. This is what our project does for market data (Alpha Vantage) and news (Tavily). You create a Named Credential for auth, a Remote Site Setting for the URL, and an Apex class with `Http.send()`.

```apex
// Example: calling an AWS Lambda function from Apex
Http h = new Http();
HttpRequest req = new HttpRequest();
req.setEndpoint('callout:My_AWS_Lambda/prod/getClientData');
req.setMethod('GET');
HttpResponse res = h.send(req);
String responseBody = res.getBody();
```

Setup: Setup → Named Credentials (for auth) + Remote Site Settings (for URL whitelist) + Apex class with @InvocableMethod.

### 4. External Services (OpenAPI)

You provide an OpenAPI (Swagger) spec for your REST API. Salesforce auto-generates Apex classes from it. You then wire those as agent actions — no hand-written code.

Setup: Setup → External Services → New → paste your OpenAPI spec URL.

### 5. MuleSoft

The enterprise integration option. MuleSoft Anypoint connects to databases (PostgreSQL, DynamoDB, Oracle), message queues (SQS, Kafka), file systems (S3, GCS), ERPs (SAP, Workday), and anything with an API. MuleSoft flows are exposed as Apex-callable actions.

### 6. MCP Server

You build or deploy an MCP server that exposes your external data as tools. Agentforce discovers the tools via the MCP protocol and can call them. Available on AgentExchange or self-hosted.

### What Our Project Uses

- Method 3 (Apex HTTP Callout) for external APIs: Alpha Vantage (market data), NewsAPI (financial news), Tavily (web search)
- Method 2 (Data Cloud CRM Connector) for syncing CRM objects into Data Cloud DLM tables
- Remote Site Settings deployed via metadata for URL whitelisting
- Named Credentials for API key storage (Tavily API key deployed to org, not committed to git)


---

## Cognitive Modes and Data Types

### Interaction Modes (How Users Talk to Agents)

| Mode | Status | Channel | How It Works |
|------|--------|---------|-------------|
| Text (NLP) | GA | Web Chat, Slack, Mobile, Agent API | Primary mode. User types natural language, agent responds with text. This is what our project uses. |
| Voice (Speech) | GA (Summer '25) | Phone (PSTN), Click-to-Talk (web), Mobile App | Agentforce Voice — real-time speech-to-text and text-to-speech. Agent handles phone calls autonomously. Supports real-time voice translation (via Google partnership). |
| Image Input | GA (Summer '25) | Web Chat, Mobile | Multimodal input — users share images in conversation. Agent analyzes image as context (e.g., photo of damaged product, screenshot of error). Uses multimodal LLMs (GPT-4o, Gemini) for vision. |
| File/Document Input | GA (Summer '25) | Web Chat, Mobile | Users upload PDFs, documents, spreadsheets. Agent reads and processes content. Example: upload insurance claim form, agent extracts fields. |
| Audio Input | GA (Summer '25) | Web Chat, Mobile | Users share audio files. Agent transcribes and processes. |
| Video Input | Limited | Via custom actions | Not natively supported in chat UI. Requires custom Apex action calling external video analysis API. |
| Proactive (Agent-Initiated) | GA (Agentforce 2dx) | Platform Events, Triggers | Agent monitors events and acts autonomously without user input. Example: portfolio drops 10% → agent proactively alerts advisor. |

Sources: [Salesforce Summer '25 Release](https://www.salesforce.com/news/stories/summer-2025-product-release-announcement/), [Agentforce Voice](https://www.salesforce.com/ap/agentforce/voice/), [Multimodal Blog](https://admin.salesforce.com/blog/2025/turn-images-pdfs-into-ai-powered-insights-with-agentforce) (content rephrased for compliance)

### Data Types Agents Can Access/Use

| Data Type | How Agent Accesses It | Example |
|-----------|----------------------|---------|
| Structured Data (CRM) | SOQL queries or CdpQuery via Apex actions | Client records, accounts, transactions, goals |
| Structured Data (External) | Data Cloud Zero-Copy, Ingestion, or HTTP callout | Snowflake tables, Redshift data, external databases |
| Unstructured Text | RAG via Data Cloud + vector search | PDFs, Knowledge articles, emails, case notes, meeting transcripts |
| Unstructured Documents | Enterprise Knowledge (Data Cloud) | Policy documents, contracts, compliance manuals — chunked, embedded, indexed |
| Images | Multimodal LLM input (GPT-4o, Gemini vision) | Product photos, damage assessments, ID verification, screenshots |
| Audio | Agentforce Voice (speech-to-text) | Phone calls, voicemails, audio messages |
| Video | Not natively supported | Requires custom Apex action calling external video analysis API |
| Embeddings/Vectors | Data Cloud vector database | Semantic search over any content — text, images, audio chunks |
| Real-time Streaming | Data Cloud streaming ingestion + Platform Events | IoT sensor data, live market feeds, social media streams |
| Files (PDF, DOCX, TXT, HTML) | Data Cloud content processing (chunking + embedding) | Uploaded documents processed into searchable chunks for RAG |

### RAG Pipeline (How Unstructured Data Reaches the Agent)

```
Upload PDF/Document → Data Cloud Content Processing
    → Text Extraction
    → Chunking (500-1000 tokens)
    → Embedding (vector conversion)
    → Vector Index (stored in Data Cloud)

User asks question → Agent → Retriever searches vector index
    → Top-K similar chunks returned
    → Chunks injected into LLM prompt as context
    → LLM generates grounded response
```

### What Our Project Uses

Text-only (NLP mode) with structured data. The agent receives text queries via chat, routes to Apex actions that query Data Cloud (structured CRM data), and returns formatted text responses. Voice, image, and RAG are future roadmap items.

# Design Doc vs Reality — Project 005

An honest assessment of what the design document specifies vs what was actually built.

---

## Gap 1: Agent API — Frontend Does Not Use the Agentforce Agent

**Design doc says:**
React frontend connects to the Agentforce agent via the Agent API (headless mode). The agent's Atlas Reasoning Engine routes queries to topics, picks the right action, and returns natural language responses with multi-turn conversation support.

```
React → Agent API → Agentforce Agent → Atlas Reasoning Engine → Topic → Apex Action → Response
```

**What was built:**
React frontend bypasses the agent entirely. It calls Apex InvocableActions directly via the standard Salesforce REST API. JavaScript keyword matching in the frontend decides which action to call.

```
React → REST API → Apex Action directly → Response (no agent, no LLM routing)
```

**What's lost:**
- No LLM-powered topic routing — dumb keyword matching instead
- No multi-turn conversation — each message is independent
- No agent personality or natural language formatting
- No escalation or off-topic handling
- No Atlas Reasoning Engine involvement

**Why:**
The Salesforce Agent API returns 404 on this Developer Edition org. The API is not available — likely requires Enterprise Edition+ or a specific Agentforce license.

**Fix:**
- Enable Agent API on the org (requires Salesforce support or different org edition)
- Or use ConnectApi.CopilotService in Apex to invoke the agent server-side
- Or use Flow-based agent invocation wrapped in an Apex REST service

---

## Gap 2: A2A Protocol — Not Implemented

**Design doc says:**
The Agentforce Orchestrator delegates to specialized sub-agents on AWS via A2A (Agent-to-Agent) protocol. The Financial Analysis Agent and Sentiment Analysis Agent are autonomous Strands agents that receive a goal, reason about which tools to use, call them in sequence, and return synthesized results.

```
Orchestrator (Agentforce) → Agent API/REST → Financial Analysis Agent (Strands, autonomous)
                                              Agent reasons → picks tools → orchestrates → returns
```

**What was built:**
Apex callout actions make direct HTTP POST calls to Lambda endpoints via API Gateway. The Lambda functions execute hardcoded Python functions — no agent reasoning, no tool selection, no autonomous orchestration.

```
Apex Action → HTTP POST → API Gateway → Lambda → Python function (direct invocation)
```

The fair_value tool does call Bedrock Claude for narrative synthesis, but it's a single LLM call with a hardcoded prompt — not an agent loop where the LLM decides which tools to call.

**What's lost:**
- No autonomous agent reasoning on the AWS side
- No dynamic tool selection — the tool is determined by the URL path, not by the agent
- No agent-to-agent communication protocol

**Why:**
Direct function approach was faster to implement. This was a shortcut.

**Fix:**
Replace Lambda functions with actual Strands Agent instances that use the @tool decorator and let the LLM decide which tools to call autonomously.

---

## Gap 3: Strands Agents SDK — Not Used

**Design doc says:**
AWS-side agents use the Strands Agents SDK (open-source Python SDK) with @tool decorator pattern.

**What was built:**
Plain Python functions called directly by the Lambda handler. No Strands SDK imported or used.

**Why:**
Strands SDK adds a pip dependency. SAM build with --use-container requires Docker/Finch which wasn't available. Direct approach avoided dependency issues.

**Fix:**
Install strands-agents in requirements.txt, use SAM build with container support or pre-build Lambda layer.

---

## Gap 4: Sprint 5 — Not Built

**Design doc says:**
Sprint 5 includes Amazon Connect (voice), Transcribe (audio to text), Textract (PDF to structured), Redshift zero-copy, EventBridge proactive triggers.

**What was built:**
Nothing from Sprint 5.

---

## Gap 5: Compliance Screening — Not a Separate Agent

**Design doc says:**
Compliance Screening is a separate Agentforce agent.

**What was built:**
An Apex InvocableAction within the IR Research Orchestrator agent — not a separate agent.

---

## Gap 6: Data Cloud — Not Used

**Design doc says:**
Data Cloud with CdpQuery, zero-copy from Redshift, vector search (RAG).

**What was built:**
Standard SOQL queries against CRM custom objects. No Data Cloud, no CdpQuery, no zero-copy, no RAG.

---

## Gap 7: React Frontend — No Real Streaming

**Design doc says:**
React app uses Agent API with SSE streaming for real-time responses.

**What was built:**
Apex action fallback with simulated streaming (word-by-word chunking with 15ms delays). No real SSE.

---

## What IS Working as Designed

| Component | Match |
|-----------|-------|
| 10 Agentforce topics | Full |
| 10 Apex InvocableActions | Full |
| 5 CRM objects + seed data | Full |
| SEC EDGAR MCP Server (Lambda) | Full |
| Market Data MCP Server (Lambda) | Partial (needs API key) |
| News Search MCP Server (Lambda) | Partial (needs API key) |
| Financial Analysis tools (DCF, comps, MC) | Full |
| Bedrock Claude for narrative/sentiment | Full |
| Langfuse tracing (both platforms) | Full |
| Langfuse prompt management | Full |
| React frontend (SLDS styled) | Full |
| OAuth2 PKCE authentication | Full |
| S3 + CloudFront hosting (CloudFormation) | Full |
| Connected App (deployable metadata) | Full |
| Named Credentials (programmatic) | Full |
| 44 test queries designed | Full |
| Reproducible deploy scripts | Full |
| Zero credentials in git | Full |

---

## Summary

The core infrastructure works: Salesforce agent with 10 topics, 5 AWS Lambda functions, Bedrock Claude integration, Langfuse governance across both platforms, React frontend on CloudFront, CloudFormation deployment. 20/20 end-to-end tests pass.

The gaps are in the agent-level architecture: the Agent API, A2A protocol, Strands SDK, separate Compliance agent, Data Cloud, and Sprint 5 services are not implemented as designed. The system works as a multi-platform tool orchestration system, but not as a multi-agent system with autonomous reasoning.

---

## Gap 8: MCP Protocol — Not Actually MCP

**Design doc says:**
Agentforce discovers and calls external tools via MCP (Model Context Protocol). MCP servers expose tool schemas for dynamic discovery.

**What was built:**
Standard HTTP REST callouts from Apex to API Gateway. The Lambda functions are regular REST APIs, not MCP servers implementing the MCP spec. No tool discovery, no MCP handshake, no MCP client in Salesforce. The mcp-config/ JSON files are documentation only.

---

## Gap 9: Salesforce as MCP Server — Not Built

**Design doc says:**
Salesforce exposes CRM data as an MCP server (get_analyst_coverage, get_client_holdings, get_meeting_history) so external agents can consume it.

**What was built:**
Nothing. Salesforce does not expose any MCP server endpoints. AWS agents cannot call back into Salesforce for CRM data.

---

## Gap 10: Research Brief Orchestration — Not Implemented

**Design doc says:**
The research_brief topic orchestrates ALL other topics: company lookup + coverage + SEC filing + market data + financial analysis + sentiment + compliance → assembles IR_Research_Note__c.

**What was built:**
No orchestration action. The research_brief topic routes to company_lookup as a fallback. No multi-action orchestration, no IR_Research_Note__c assembly.

---

## Gap 11: Amazon Comprehend — Not Used

**Design doc says:**
Sentiment Analysis Agent uses Amazon Comprehend for entity extraction and sentiment analysis.

**What was built:**
All sentiment analysis uses Bedrock Claude directly. Amazon Comprehend is not called anywhere.

---

## Gap 12: Channels — Only React Frontend

**Design doc says:**
Three channels: Web Chat (Experience Cloud), Slack, Agent API (React).

**What was built:**
React frontend only. No Experience Cloud chat widget connected to this agent. No Slack integration.

---

## Gap 13: Multimodal — Not Implemented

**Design doc says:**
Phase C: earnings call audio (Transcribe), 10-K PDF extraction (Textract), voice queries (Amazon Connect).

**What was built:**
Text only. No audio, no PDF, no voice. Sentiment analysis uses hardcoded sample transcript text.

---

## Gap 14: Real-Time Streaming — Not Implemented

**Design doc says:**
Amazon Kinesis for real-time market data streaming into Data Cloud.

**What was built:**
No streaming. Market data from Alpha Vantage API (when configured) or empty.

---

## Gap 15: Proactive Triggers — Not Implemented

**Design doc says:**
EventBridge rules trigger Salesforce Platform Events when earnings dates approach, causing proactive analyst alerts.

**What was built:**
No EventBridge. No Platform Events. No proactive alerts. Agent only responds to user queries.

---

## Gap 16: Private Connect / PrivateLink — Not Implemented

**Design doc says:**
Production uses Salesforce Private Connect + AWS PrivateLink (no public internet).

**What was built:**
All traffic over public internet with TLS. Documented as "dev mode" — acceptable but production path not implemented.

---

## Gap 17: MNPI Isolation — Not Enforced

**Design doc says:**
MNPI never leaves Salesforce. Information barriers at Orchestrator level. AWS agents never receive MNPI data.

**What was built:**
Compliance screening runs on Salesforce only (correct). But no actual MNPI data exists, no information barrier logic, no enforcement mechanism. Design documented but not enforced in code.

---

## Gap 18: Bidirectional Communication — One-Way Only

**Design doc says:**
Bidirectional: Agentforce → Bedrock agents AND Bedrock agents → Agentforce via Agent API for CRM data.

**What was built:**
One-way only: Salesforce → AWS. AWS Lambda functions cannot call back into Salesforce. No Connected App for AWS-to-SF OAuth, no Apex REST endpoints exposed.

---

## Complete Gap Count: 18

| Category | Gaps |
|----------|------|
| Agent Architecture | 1 (Agent API), 2 (A2A), 3 (Strands SDK), 5 (Compliance Agent) |
| Protocols | 8 (MCP), 9 (SF as MCP Server), 18 (Bidirectional) |
| Data | 6 (Data Cloud), 14 (Kinesis streaming) |
| Features | 10 (Research Brief), 11 (Comprehend), 12 (Channels), 13 (Multimodal), 15 (Proactive) |
| Infrastructure | 4 (Sprint 5), 7 (SSE streaming), 16 (Private Connect) |
| Security | 17 (MNPI enforcement) |

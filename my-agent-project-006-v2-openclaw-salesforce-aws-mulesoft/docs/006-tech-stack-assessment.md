# 006 Tech Stack Assessment — Every Choice Justified

> Date: April 8, 2026
> Purpose: Assess every technology choice in the 006 stack. Challenge defaults. Replace where better options exist.

---

## The Principle

Every component must earn its place. If the LLM already does it well, don't add a separate service. If a specialized service is 10x cheaper or 10x faster for the same quality, use it. No resume-driven architecture.

## 1. Sentiment Analysis: DROP Comprehend and FinBERT, USE Claude

### Why the Original Design Was Wrong

The design doc specified Amazon Comprehend for sentiment + FinBERT as backup. Recent research (arxiv 2505.16090, arxiv 2506.04574, Microsoft benchmark 2025) shows LLMs significantly outperform traditional NLP tools on financial sentiment — especially on nuanced earnings call language where management uses strategically ambiguous phrasing.

Comprehend is general-purpose NLP. It misclassifies "revenue growth decelerated to 25%" as negative when it's actually positive for a company growing faster than peers. FinBERT handles binary (positive/negative) well but fails on multi-dimensional sentiment (tone shifts, hedging, forward-looking caution).

Claude — which 006 already uses for everything else — handles financial sentiment natively. No separate service needed.

| Aspect | Comprehend | FinBERT | Claude (Bedrock) |
|--------|-----------|---------|-----------------|
| Financial nuance | Poor — general-purpose | Good for binary | Best — understands hedging, guidance language |
| Multi-dimensional | No — single score | No — 3 classes | Yes — 10+ dimensions in one call |
| Cost per 10K tokens | ~$0.10 | Free but Lambda hosting | ~$0.003 (Haiku) to $0.015 (Sonnet) |
| Additional infra | Comprehend API | Lambda + model hosting | Already running — zero additional |

The sentiment-analysis skill becomes a prompt template, not a service wrapper:

```python
# Before: 3 separate service calls
comprehend.detect_sentiment(text)
comprehend.detect_entities(text)
comprehend.detect_key_phrases(text)

# After: 1 LLM call, richer output
claude.invoke("""
Analyze this earnings call transcript for:
1. Overall sentiment (bullish/neutral/bearish) with confidence
2. Management tone: confident, cautious, defensive, evasive
3. Key tone shifts (where did sentiment change and why)
4. Forward guidance sentiment vs backward-looking
5. Hedging language or deflection patterns
6. Key drivers of sentiment

Transcript: {text}
""")
```

One call. Richer output. Lower cost. No additional service.

---

## 2. Speech-to-Text: KEEP Transcribe

Amazon Transcribe stays. Earnings calls are clean conference audio — Transcribe handles this well. The accuracy gap vs Whisper is ~2-3% on clean audio, not worth the complexity of self-hosting Whisper on GPU Lambda. Native AWS integration (S3 trigger, IAM auth) is a real advantage. Transcribe output feeds into Claude for sentiment — the LLM compensates for minor transcription errors.

If accuracy becomes an issue on specific calls, Whisper via API is the fallback.

---

## 3. Document Processing: KEEP Textract, but MINIMIZE its use

Key insight: 90%+ of SEC EDGAR filings are HTML, not scanned PDFs. For HTML filings, we don't need OCR at all — just parse the HTML directly and send to Claude.

Textract is only needed for the occasional scanned PDF or image-heavy filing. Claude vision handles complex layouts better than Textract alone (aimultiple.com benchmark: Claude Sonnet showed highest accuracy across document quality levels).

```
SEC EDGAR filing (HTML, 90%) -> parse HTML directly -> Claude for analysis
SEC EDGAR filing (PDF, 10%)  -> Textract for tables -> Claude for interpretation
Earnings call (audio)        -> Transcribe -> Claude for sentiment
```

---

## 4. LLM: Tiered Model Strategy (Sonnet 4.6 + Haiku 4.6)

Both latest-generation models on Bedrock. Don't worry about cost — optimize for quality and simplicity.

```
L1-L2 (simple lookups, assembly): Claude Haiku 4.6
  - Fast, capable, handles tool use well
  - 80% of daily query volume
  - Keeps L1 responses snappy (<2s)

L3-L5 (analysis, pipeline, actions): Claude Sonnet 4.6
  - Best reasoning for DCF, compliance, multi-step analysis
  - Full research briefs, trade execution decisions
```

The intent router classifies query complexity and selects the model. Haiku 4.6 for speed on simple queries, Sonnet 4.6 for depth on everything else.

---

## 5. Agent Runtime: KEEP OpenClaw on AgentCore

No change. This is the right choice. Multi-channel gateway (12+ channels) and AutoResearchClaw pipeline are the two things that make 006 different from 005. Strands doesn't have either. AgentCore is confirmed production-ready with official AWS deployment guides and CI/CD templates.

---

## 6. MCP Servers: KEEP Lambda + API Gateway

No change. MCP servers are stateless request-response tools. Lambda is the natural fit. Cold starts (1-3s) are acceptable within a pipeline that takes minutes. For L1 queries where users expect instant responses, use Lambda SnapStart or provisioned concurrency if cold starts become noticeable.

---

## 7. Data APIs: KEEP, but paid tiers from day 1

- Alpha Vantage Standard ($49.99/mo) — free tier (25 calls/day) is too low for development
- Polygon.io Starter ($29/mo) — backup, especially for options data
- EODHD All-World ($79.99/mo) — historical data for DCF and backtesting
- Tavily Pro ($50/mo) — purpose-built for AI agents, structured results
- SEC EDGAR — free, public, excellent. No change.
- NewsAPI.org — free tier for backup. No change.

---

## 8. Frontend: KEEP entire 005 V2 stack

Zustand 5 (state), Recharts 2.15 (charts), SLDS 2.25 (design system), Vite 6 (build), React 19 + TypeScript. All proven in 005 V2. No changes needed. Already assessed in the frontend assessment doc.

---

## 9. Observability: KEEP Langfuse (self-hosted)

Self-hosted in same VPC — no data leaves the network (FSI requirement). Scoring API is exactly what the evaluation strategy needs. OpenClaw has proven Langfuse integration. CloudWatch stays for infrastructure monitoring (Lambda, API Gateway, AgentCore health). Different layers, both needed.

---

## 10. CRM: KEEP Salesforce FSC

Non-negotiable. System of record for client data, compliance, audit trail. FSC provides FinServ__* objects. Use FSC trial org for prototyping, scratch org for ongoing development.

---

## Revised Stack Summary

| Component | Original | Revised | Change |
|-----------|---------|---------|--------|
| Sentiment Analysis | Comprehend + FinBERT | Claude (Bedrock) | REPLACED — LLM is better, cheaper, simpler |
| LLM | Sonnet 4 (all queries) | Sonnet 4.6 + Haiku 4.6 (tiered) | ADDED tier — Haiku for speed on L1-L2 |
| Document Processing | Textract | Textract (PDF only) + HTML parser + Claude | OPTIMIZED — skip Textract for 90% of filings |
| Speech-to-Text | Transcribe | Transcribe | NO CHANGE |
| Agent Runtime | OpenClaw on AgentCore | OpenClaw on AgentCore | NO CHANGE |
| MCP Servers | Lambda + API Gateway | Lambda + API Gateway | NO CHANGE |
| Market Data | Alpha Vantage | Alpha Vantage (paid from day 1) | UPGRADED tier |
| SEC Filings | SEC EDGAR | SEC EDGAR | NO CHANGE |
| News | Tavily | Tavily | NO CHANGE |
| Frontend | React + Zustand + Recharts + SLDS | Same | NO CHANGE |
| Observability | Langfuse + CloudWatch | Langfuse + CloudWatch | NO CHANGE |
| CRM | Salesforce FSC | Salesforce FSC | NO CHANGE |

### Removed

- Amazon Comprehend (LLM does it better)
- FinBERT self-hosted (LLM does it better)
- Separate sentiment Lambda function (now a prompt template)

### Added

- Claude Haiku 4.6 tier for L1-L2 queries
- HTML parser for EDGAR filings (skip Textract for 90% of filings)

### Net Effect

- 2 fewer AWS services (Comprehend, FinBERT hosting)
- 1 fewer Lambda function
- Simpler architecture
- Better sentiment quality (Claude > Comprehend on financial text)
- Single deployment — no dev/staging/production split. One environment, reproducible from scratch.

---

## Deployment Model: Single Environment, Reproducible

No dev vs production. One deployment. Everything scripted so it can be torn down and rebuilt from zero.

```
One AWS account
  -> One AgentCore deployment (OpenClaw)
  -> One set of Lambda MCP servers (SAM template)
  -> One Langfuse instance (EC2 or Fargate)
  -> One S3+CloudFront (frontend)

One Salesforce org
  -> Scratch org (sf org create) or FSC trial
  -> Seed data via Apex scripts
  -> Custom objects via metadata deploy

Reproducibility:
  git clone -> sf org create -> sf project deploy -> sam deploy -> done
  Everything in git. Nothing manual. Nothing click-ops.
```

---

## Monthly Cost Estimate

| Component | Cost |
|-----------|------|
| Bedrock — Claude Sonnet 4.6 (L3-L5, pipeline) | Pay-per-use |
| Bedrock — Claude Haiku 4.6 (L1-L2) | Pay-per-use |
| Bedrock — Guardrails | Included |
| Lambda (3 MCP servers) | ~$5 |
| API Gateway | ~$3 |
| Transcribe (occasional) | ~$3 |
| Textract (occasional PDFs) | ~$2 |
| Alpha Vantage Standard | $50 |
| Polygon.io Starter | $29 |
| EODHD All-World | $80 |
| Tavily Pro | $50 |
| Langfuse (self-hosted) | ~$30 |
| S3 + CloudFront | ~$5 |
| AgentCore (serverless) | Pay-per-use |
| Salesforce (scratch org) | $0 |

Cost is not a constraint. Quality and reproducibility are.

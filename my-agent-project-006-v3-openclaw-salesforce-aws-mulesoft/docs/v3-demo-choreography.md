# 006 V3 — Demo Choreography

> **Audience:** the person who will stand on stage
> **Purpose:** how to make the V3 demo world-class. Not what we build — how we *show* it.
> **Sibling doc:** `v3-narrative-arc.md` (architecture + narrative + deliverables)
> **Status:** research-grounded plan, no build yet.

---

## What Deep Research Shows About Winning AI Demos in 2026

Seven signals from what's actually landing with enterprise panels this year. Content below is rephrased from industry sources listed at the bottom; every claim is attributable.

**1. Demos have matured past "look, it works."** The strongest 2026 enterprise AI demos emphasize *controlled autonomy* — deterministic process logic combined with LLM reasoning, traceability to source data, and visible human inspection points. The bar is no longer a working agent; it's an agent that a compliance officer would let near production. [Forrester on Finovate Europe 2026](https://www.forrester.com/blogs/finovateeurope-2026-from-ai-hype-to-bank-ready-execution/)

**2. Showing the work is the new feature.** Luke Wroblewski's February 2026 piece — *Showing the Work of Agents in UI* — crystallizes it: an AI product becomes agentic when the model plans which tools to use, configures them, and decides next steps. The UI must *expose* that plan-execute-observe loop, not hide it. Black-box demos are actively distrusted in 2026. [LukeW](https://lukew.com/ff/entry.asp?2142=)

**3. The "controlled autonomy" frame is how you beat the hallucination question.** Demos that show deterministic guardrails + LLM reasoning + explicit override points are read as bank-ready; demos that show only reasoning are read as toys. Humans repositioned from *operators* to *validators and overseers* is the operating model enterprises are buying. [Forrester, as above](https://www.forrester.com/blogs/finovateeurope-2026-from-ai-hype-to-bank-ready-execution/)

**4. Start with shock and awe in the first 60 seconds.** Kawasaki's rule, unchanged across decades: you have about a minute to captivate. Don't build to a crescendo — lead with the most dramatic capability. [Guy Kawasaki, How to Be a Demo God](https://guykawasaki.com/how-to-be-a-demo-god/)

**5. Cut jokes, cut jargon, cut duos, cut questions mid-flow.** Single presenter. Simple words. Take questions only at the end. A failed joke costs more momentum than a successful one earns. [Kawasaki, as above](https://guykawasaki.com/how-to-be-a-demo-god/)

**6. The AWS Wealth Management AI Advisor demo sets the bar specifically for our use case.** Celent's writeup of the re:Invent AWS booth demo describes what executives are seeing: agent digests earnings calls, 10-Ks, portfolio data; produces instantaneous insights; runs on Bedrock with Claude. That's *exactly* what our Sarah narrative does — but our platform adds the three-persona Workflow 360 angle that AWS doesn't show. The panel will have seen AWS's version. We need to be visibly deeper. [Celent on AWS AI Advisor](https://www.celent.com/en/insights/414830290)

**7. Claude Sonnet 4.5/4.6 credibility is already established.** Sonnet 4.5 leads the Finance Agent benchmark at 55.3% accuracy; Sonnet 4.6 in Feb 2026 beat Opus 4.6 on financial benchmarks at 1/5th the cost. The panel will not challenge the model choice. Don't waste demo time on "why Claude." [em360](https://em360tech.com/tech-articles/claude-4-5-financial-ai), [prompted.research](https://promptedllc.com/research/the-88-financial-ai-deployment-paradox)

*Content was rephrased for compliance with licensing restrictions.*

---

## The Seven Principles Our Demo Must Follow

Distilled from the research above, mapped to V3.

1. **Open with a 60-second shock-and-awe.** Not setup, not agenda. The first minute must show something the panel hasn't seen before. (See "The Cold Open," below.)
2. **Show the work, always.** Every LLM decision has a visible trace. No black boxes on any screen at any point. If the agent is thinking, the audience sees what it's thinking.
3. **Frame controlled autonomy, not autonomy.** Every time an agent decides, a human gate is visible. Humans are validators, not operators. The trust spine is the star — not the model.
4. **One presenter, one mic, zero jokes.** Single voice. Plain language. Take no panel questions until the end, and announce that boundary up front.
5. **Every demo action resolves to a tangible artifact.** Sarah's brief becomes a visible `Research_Brief__c` row. The RM's call list cites it. The trade leaves a `IR_Audit_Log__c` row the panel can click. Nothing floats.
6. **The three-persona story is our moat.** AWS's and Anthropic's demos are single-persona. Ours is the only one that traverses analyst → advisor → client → settled trade. Lean into what only we can show.
7. **End with one more thing.** Jobs's trick, still works. After the main act, show a single piece of depth that makes the panel realize the platform has more in it than the demo covered.

---

## The Four-Act Demo (15 Minutes, Live)

Replaces the old "three queries" structure with a tighter, research-informed arc. All runs on V3 as built in the narrative doc — no new scope introduced here, just choreography.

### Act 0 — The Cold Open *(0:00–1:00)*

No intro. No agenda. No "today I'll show you."

The screen is already on Sarah's research terminal. The clock reads 6:45 AM Singapore. The query is already typed:

> `Research NVDA ahead of earnings. Pull 10-Q risk factors, score 30-day sentiment, check restricted list, flag MNPI. Brief for RM consumption.`

Press Enter. Within two seconds, **the audit strip shows five tool-call spans opening in parallel** — market, filings, sentiment, compliance, statement. Not sequential. Not a waterfall. Five Sonnet-4.6 sub-agents working concurrently via `asyncio.gather`. The brief begins streaming a moment later, synthesized by the research-orchestrator as each specialist returns.

While it streams, say exactly this, slowly, one sentence per phase:

> *"This is a senior research analyst at 6:45 AM in Singapore. NVDA reports in 73 minutes. Watch five specialist agents work in parallel — market, filings, sentiment, compliance, statement analysis. The orchestrator synthesizes. Every sentence cites a source."*

Total words spoken: 37. The brief finishes around **0:15 — fifteen seconds**. Let the audit strip visibly catch up for ten seconds of silence. Then:

> *"Fifteen seconds. A compliance-cleared, MNPI-filtered, audit-logged pre-earnings brief with citations back to the 10-Q. Five sub-agents, one synthesis, about eleven cents in token cost. That's what the rest of this demo is built on."*

**Why this opens the demo:** two things land in the first minute that no competitor demo has shown — true multi-agent parallelism visible in the audit strip (not a single agent doing sequential tool use), and citation-bound generation so every sentence is defensible. LukeW's "show the work" principle is literal; Kawasaki's shock-and-awe rule is the parallel fan-out. The panel reads "this isn't a chatbot demo" within 60 seconds.

### Act 1 — The Handoff *(1:00–5:00)*

Split-screen: Sarah's screen on the left (brief visible, static now), RM's screen appearing on the right.

Switch to the RM screen. Say:

> *"An hour later. Different person, different role, different screen, same platform."*

Type into the RM's query bar:

> `Which of my clients have NVDA exposure above 5% and haven't been contacted in 7 days?`

Result lists 3 clients. Each row carries an **inline citation** — *"Based on Sarah Chen's 7:08 AM brief"* — as a clickable chip. Click one. A pane opens showing the brief. Close it.

> *"The brief isn't attached to an email. It isn't in a folder. It's a first-class record in Salesforce — `Research_Brief__c` — joined at the data layer to every position, every client, every household in the RM's book. Sarah wrote it. The platform made it contextually available to exactly the RMs whose clients have NVDA exposure. Nobody emailed anything."*

Then, the client view appears. WhatsApp-style interface on the right edge of the screen.

Client message arrives live (confederate sends it):

> `Should I be worried about NVDA? My friend said semis are crashing.`

Client-liaison responds. The message cites Sarah's brief; offers to schedule a call; carries a disclaimer.

> *"The same research. Three personas. Three interfaces. One audit trail. That's what Workflow 360 actually is."*

**Why this act:** it's the differentiator. No other vendor demo shows analyst-to-advisor-to-client on one platform with citations stitched through. This is the 4-minute stretch where the panel starts realizing what they're looking at.

### Act 2 — The Trust Spine *(5:00–11:00)*

This is the panel wildcard. Hand someone on the panel the keyboard. Say:

> *"Type any reasonable sell instruction for the Patel household. You're the RM. Go."*

Whatever they type, the agent produces a structured ActionPlan. The top of the screen shows the **seven-gate progress tracker**:

```
① Guardrails  ② MNPI filter  ③ Compliance  ④ HITL  ⑤ Dual-auth  ⑥ MuleSoft  ⑦ Audit
```

Each gate lights up in real time as it passes. The RM sees an approval dialog inline (no modal). HITL fires for them to click Approve. If their instruction crosses the $500K/$100K threshold (which we'll arrange by suggesting notional), dual-auth triggers and a second senior compliance user — prearranged on a second laptop visible on stage — approves.

OFAC screens. Alpaca paper fills. Dwolla initiates. Audit stitches.

> *"Two humans. One machine. Four external systems. One audit trail. Seven minutes from the query to a settled regulated transaction."*

Click the `IR_Audit_Log__c` record that just appeared. Show the cross-stitching: research_brief_id → client_contact_id → the RM's query → the HITL approval → the compliance decision → the trade ID → the wire reference. All linked, all queryable, all audit-ready.

> *"A compliance officer can replay every decision the agent and the humans made, in order, from a single record. That's the difference between a chatbot that can trade and a platform a bank would let near production."*

**Why this act:** the research is unanimous — *controlled autonomy* is what enterprises buy in 2026, not raw autonomy. Showing seven gates light up on a panelist's own query is the most powerful trust demonstration we can stage.

### Act 3 — One More Thing *(11:00–13:00)*

Jobs's trick, applied honestly. Show one capability that extends the platform beyond what the main demo covered.

Options (pick one based on the room):

- **Option A — The inversion.** A client message triggers analyst work. *"Same agent. Reverse the flow. Client asks about a ticker Sarah hasn't researched. Watch what happens."* Show Narrative 2 compressed to 90 seconds — `Client_Inquiry__c` appears in Sarah's queue, she accepts, new brief gets published, RM sees the answer.
- **Option B — The network effect.** *"One more thing. The platform gets smarter over time."* Show Sarah's "Client demand signals" tab with the pre-seeded China tech row. Click Accept. New brief publishes. *"Three days of client behavior, one research agenda shift."* (Disclose: this uses pre-seeded data; the behavioral clustering is V4.)
- **Option C — The alert.** *"One more thing. The platform doesn't wait for queries."* Hit the "Simulate NVDA -8%" button. Alerts populate RM queues with policy gates. (Disclose: staged trigger.)

**My recommendation: Option A.** It's the strongest because it runs live on real V3 infrastructure (no staging), and it demonstrates the feedback loop — the thing that makes Workflow 360 an *ecosystem* rather than a one-way waterfall.

### Act 4 — The Close with Three Hard Numbers *(13:00–15:00)*

Three slides. Not a deck — three slides total. Each one answers the question the executive is already asking themselves.

**Slide 1 — The ROI arithmetic.**

Full screen. No chart. One number:

```
1,600×
  $180/hour senior analyst → $0.11 research brief
  same output, audited, cited, compliance-cleared
```

Say once:

> *"Eleven cents. A senior analyst hour is $180. That's 1,600 times. It's not a productivity improvement. It's a different economic model for research."*

Pause.

**Slide 2 — The 90-day deployment commitment.**

```
90 days to your top quartile RMs.
  Weeks 1–3: your 10 holdings in our rehearsal org
  Weeks 4–6: parallel run with 10 analysts, 3 RMs
  Weeks 7–9: compliance sign-off, audit review, OFAC & SDN live
  Weeks 10–12: staged rollout to 50 RMs
One engineer from you. Three from us. No rip and replace.
```

Say once:

> *"This is not a strategy deck. This is a commitment. Your top quartile is running on this in ninety days, or you call us."*

**Slide 3 — The compliance reframe.**

```
Your CCO will approve this faster
  than your current manual process.
Every decision is deterministic. Every source is cited.
Every gate is audited. Replay from a single record.
You cannot say that about today's analyst workflow.
```

Say once:

> *"The thing you're worrying about — your compliance head killing this — is backwards. They're going to want this before you do. Deterministic replay, cited sources, seven-gate audit. None of that exists in a senior analyst's Word doc today."*

Then close. No slides. Look at the panel:

> *"Three personas. One agent runtime. One system of record. One audit trail. Seventeen sub-agents, five in parallel on every brief. Reads direct. Writes gated. Research cites itself, clients get real answers, trades clear with two humans in the loop. Built on OpenClaw, Bedrock, Salesforce, MuleSoft — all things you already buy. Ninety days. Sixteen hundred times. Your CCO's ally. That's 006 V3."*

Pause. Long pause.

> *"Questions."*

**Why this close:** the research is clear — demos that end with specific numbers the panel can quote back at the next meeting are what get pilots signed. Three slides, three numbers, three reframes. No feature list. No roadmap. No "thank you for your time." The last thing they hear is the word *questions* — which puts them, not you, on the next move.

**Pre-demo prep that makes Slide 2 honest:** before the panel walks in, the rehearsal org must be loaded with **the firm's own top 10 holdings**, not our demo tickers. The BYOD (bring-your-own-data) step happens 48 hours before the meeting. We ask for their 10-K watchlist; we ingest into the filings corpus overnight; we re-run the cold-open query against NVDA plus one of their top holdings during rehearsal. When Slide 2 says "your 10 holdings in our rehearsal org," it's not aspirational — we've already done it. The executive sees their firm's actual book in the demo, not generic names. That's the bridge from "impressive" to "I want it."

---

## The Depth Layer — What Makes This Demo Deep, Not Just Flashy

The panel's most sophisticated members (the CTO, the compliance officer, the risk head) are looking for depth signals under the polish. Ten places the demo shows depth the research competitors don't:

1. **The audit strip is literal.** Every Langfuse trace is visible. The panel can see timing, token counts, tool latencies. Not a summary — the actual ledger.
2. **Sharing rules are real.** When the RM's screen is showing Patel's positions, it's because FSC sharing rules let them see it. Switch to a different RM account mid-demo for 10 seconds to show the book scope changes. No other demo does this.
3. **Cross-persona audit linkage is shown by clicking, not by slide.** The panel sees the SObject chain. They can SOQL it themselves if they ask.
4. **MuleSoft earning its keep is visible.** The seven-gate tracker makes the distinction between reads (fast, direct) and writes (gated, orchestrated) unmissable. Reads never touch MuleSoft; writes always do. The architecture reads itself.
5. **MNPI filter is shown by failure, not by success.** If appropriate to the room: have the RM type a query that would surface MNPI data. Show the filter cut it. *"You just saw what the panel didn't hear."*
6. **Cost comes up on its own.** When the token count in the audit strip hits $0.11 for the full brief, mention casually: *"This brief costs eleven cents to produce. A senior analyst's hour costs $180. That's the ROI without any other argument."*
7. **The compliance officer's question is pre-answered.** Before the Q&A, say once: *"Every action you saw wrote to `IR_Audit_Log__c`. Replay is deterministic from that ledger. That's FINRA-ready by design, not by patch."*
8. **Citation chips are clickable and cite primary sources.** In Act 0, after the brief streams, click one citation chip. A side pane opens showing the actual 10-Q section the sentence was drawn from — Item 1A Risk Factors, page 12, paragraph 3. *"Every sentence in this brief cites a source chunk. Unsourced sentences are cut server-side before you see them. A junior analyst's brief ten minutes of manual verification just happened automatically at retrieval time."* This is the RAG depth signal — no one else in financial-services demos is enforcing citation-bound generation visibly.
9. **A chart in the brief is not LLM-drawn.** Click the bar chart that appeared in Sarah's brief showing NVDA's revenue mix. *"The LLM didn't draw this. It emitted chart intent — chart type, source table ID, segments to highlight. A deterministic renderer loaded the parsed 10-Q table and drew it. The numbers in this chart are the exact numbers a junior analyst would have read from the 10-Q tab — because they came from the 10-Q tab."* Hover a segment → source citation. Click a segment → drill into the line-item. Depth visible without explanation.
10. **Financial statement analysis is deterministic math, narrated by LLM.** When the brief shows "gross margin improved from 56% to 75% over five years," say: *"Those numbers came from a Python calculator, not the model. The model decided to compare NVDA's five-year gross margin to AMD's and to narrate the comparison — but the numbers are computed from four 10-Qs and reproducible from any workstation."* If the panel has time, pull up the Langfuse trace showing `financial-statement-analysis.compare_peers` as a distinct span with the Pydantic model output. *"A junior builds 'the agent calculates gross margin.' We build deterministic calculators the agent orchestrates. The numbers are audit-safe."*

These ten are deep cuts — the panel members who know what to look for will see them; the ones who don't will still feel the overall density.

---

## What We Don't Do on Stage

Hard rules, informed by the research on what kills demos.

- **No "this would be cool if..." language.** Only what's running.
- **No roadmap slides.** Narratives 3 and 4 (from the narrative arc doc) sit in the deck as optional backup, not main-path.
- **No "imagine if." Ever.** If we'd be imagining, we cut the moment.
- **No duo presenting.** One person. Kawasaki's rule. The second laptop on stage is for the senior compliance dual-auth approval — visibly a different person, different cursor, not a co-presenter.
- **No panel questions during the demo.** State the rule at the cold open end: *"I'll take questions after. Interruptions cost 90 seconds each and we have a lot to show."*
- **No fake latency.** If a tool is slow, we let it be slow and say *"this is real market data coming back from Finnhub right now"* while it loads. Real latency is trust; fake smoothness is suspicious.
- **No pre-recorded video as fallback unless the live agent fails twice.** Fallback order: live → live retry with a different query → pre-recorded. If we show video, we say: *"this is a recording — the live systems are behind us."*

---

## Demo Infrastructure (What Gets Built Just for the Demo)

Distinct from V3 platform scope. These exist only to make the demo itself sharp.

1. **Warm-start harness.** Before the panel walks in, a script fires a dummy query on each persona to warm AgentCore, connect WebSockets, pre-auth the SF Auth Proxy. Cold starts are a demo killer.
2. **Confederate channel.** A team member's phone, pre-logged into WhatsApp Business (or the mockup client channel), ready to send the client message on cue in Act 1. Rehearsed timing.
3. **Second compliance laptop.** Visible on stage, logged in as a `Senior_Compliance_Approver` permset user. For dual-auth moment in Act 2.
4. **Audit strip component.** The Langfuse-trace-to-visible-strip UI. Built once, embedded in both agent screens.
5. **Seven-gate progress tracker.** React component, WebSocket-fed from AgentCore skill-invocation events. The literal visual of the trust spine.
6. **Rehearsal org with deterministic seed data.** The Patel household, positions, the 30-day news window, a pre-loaded OFAC SDN JSON. All stable. No surprises.
7. **Kill switch.** Panic button the presenter controls. Cuts to a pre-recorded video of the same demo flow if anything catastrophic happens mid-stage. Never shown unless needed.

Total demo infrastructure build: ~400 lines on top of V3 platform scope. Most of this is React (audit strip, seven-gate tracker) and rehearsal scripts.

---

## Rehearsal Plan

- **Week 1:** end-to-end on the happy path, no audience. Timing pass — every act within its window.
- **Week 2:** adversarial panel. Internal review with hostile Q&A ("what if Alpaca is down?"). Harden talk track.
- **Week 3:** full dress with confederate on client channel, compliance dual-auth on second laptop, real Finnhub traffic, live Bedrock calls. Record it. Watch the recording.
- **Week 4:** the run. Warm-start script fires 10 min before doors. Presenter has coffee, no notes, one rehearsed paragraph for the close.

---

## Success Criteria

The demo wins if, within 24 hours, at least three of the following happen:

- A panel member quotes the closing paragraph back verbatim.
- A panel member asks specifically about `Research_Brief__c` or the cross-persona audit stitching — signaling they dug into the depth layer.
- A technical member asks to SOQL the audit log themselves.
- The room asks to see Narrative 2 (the inversion) unprompted — signals the "one more thing" landed.
- The compliance officer asks *no* questions during Q&A — because every compliance question was pre-answered on stage.

Anything less is a real-but-not-great demo. We'll refine for the next room.

---

## Sources (rephrased content above attributable to these)

- [Forrester — FinovateEurope 2026: From AI Hype to Bank-Ready Execution](https://www.forrester.com/blogs/finovateeurope-2026-from-ai-hype-to-bank-ready-execution/)
- [Luke Wroblewski — Showing the Work of Agents in UI, February 2026](https://lukew.com/ff/entry.asp?2142=)
- [Guy Kawasaki — How to Be a Demo God](https://guykawasaki.com/how-to-be-a-demo-god/)
- [Celent — AWS Wealth Management AI Advisor review](https://www.celent.com/en/insights/414830290)
- [em360 — Claude 4.5 Raises the Bar for Financial AI](https://em360tech.com/tech-articles/claude-4-5-financial-ai)
- [prompted.research — The 88% Financial AI Deployment Paradox (Sonnet 4.6 cost claim)](https://promptedllc.com/research/the-88-financial-ai-deployment-paradox)
- [SalesforceBen — Dreamforce 25 Agentforce keynote roundup (observability + Moments)](https://www.salesforceben.com/complete-roundup-of-the-agentforce-keynote-at-dreamforce-25/)

*Content was rephrased for compliance with licensing restrictions.*

---

*Choreography locked. No build yet. Rehearsal begins when platform is feature-complete.*

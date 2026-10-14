# 006 V3 — Client (End-Investor) Persona Feature Map

> **Date:** 2026-05-01
> **Author:** research study, not a build plan
> **Audience:** exec panel, product, engineering steering
> **Scope:** `fsi-client-liaison` persona only (Eleanor Vance). What a real HNW wealth-management client expects from a digital channel, what V3 already ships for the client surface, what's missing, what's demo-worthy, and an executable feature backlog.
>
> **Status:** research → prioritized backlog. No code changed.
> **Companions:** `v3-research-analyst-feature-map.md` (Sarah), `v3-advisor-feature-map.md` (Marcus), `v3-client-there-vs-not.md` (at-a-glance).

---

## 1. What an HNW wealth-management client actually wants

Based on [Backbase's private banking modern digital guide](https://www.backbase.com/blog/the-ultimate-guide-for-modern-private-banking), [Cutter Associates on HNW/UHNW client experience](https://www.cutterassociates.com/insights/the-evolution-of-the-wealth-management-client-experience), [BeckDigital's UX research on HNW clients](https://beckdigital.com/insights/ux-for-high-net-worth-wealth-management/), [Finantrix's wealth management platform buyer's guide](https://www.finantrix.com/buyer-guides/wealth-management-platforms-private-banks), and public-facing product descriptions from [J.P. Morgan](https://privatebank.jpmorgan.com/gl/en/about-us/jp-morgan-mobile-app), [Standard Chartered Private Bank](https://www.sc.com/en/wealth-retail-banking/private-banking/private-bank-app/), and [Barclays Private Bank](https://privatebank.barclays.com/digital-banking/the-barclays-app/). Content paraphrased for licensing compliance.

### 1.1 Who the client is

The client persona in 006 V3 is Eleanor Vance — a HNW client with a sizable portfolio, an assigned RM (Marcus), and a modest digital appetite. Real-world analogue: mass-affluent to lower-HNW investor ($500k to $20M investable). Key traits:

- **Not a DIY investor.** Trusts the RM to make recommendations; does not want a Robinhood-style trading screen.
- **Relationship-anchored.** Values the RM relationship; digital is an *augmentation*, not a replacement.
- **Privacy-conscious.** Wants discretion. Disclosures, disclaimers, and secure channels are non-negotiable.
- **Time-poor.** Expects immediacy for simple things (balance, statement, wire status), tolerates slower for complex things (investment advice).
- **Channel-flexible.** Will use whatever channel is easiest — mobile app, WhatsApp, SMS, email, phone. Does not want to log in to a new portal just because the firm built one.

### 1.2 What an HNW client actually does via digital channels

Synthesizing J.P. Morgan Mobile, Standard Chartered Private Bank App, Barclays Private Bank App, and RMB Private Bank's digital channel descriptions, the top 10 actual digital activities for HNW clients are:

| Rank | Activity | Frequency | Channel today |
|---|---|---|---|
| 1 | Check portfolio balance / high-level allocation | Daily–weekly | Mobile app |
| 2 | Read / download statements, trade confirms, tax docs | Monthly–quarterly | Mobile app / email |
| 3 | Secure message with RM (ask a question, share an idea) | Weekly | In-app secure chat or WhatsApp |
| 4 | Schedule a call with RM | Monthly | App calendar / email |
| 5 | View recent transactions / trade history | Weekly | Mobile app |
| 6 | Execute simple banking (wire, bill pay) | Monthly | Mobile app |
| 7 | Review performance vs. benchmark | Quarterly | Mobile app / emailed report |
| 8 | Approve or acknowledge trade recommendations from RM | Situational | Email / secure message |
| 9 | Read firm research published by the house | Situational | Email / app feed |
| 10 | Upload KYC / regulatory documents | Annually | Mobile app upload |

Note: **actual trade execution is rare** for HNW. Most trades are RM-initiated with client acknowledgement. Only mass-affluent robo-style clients self-trade.

### 1.3 What they explicitly do NOT want

From HNW UX research ([BeckDigital](https://beckdigital.com/insights/ux-for-high-net-worth-wealth-management/), Cutter Associates, wealth-management.com on UHNW digital):

1. **A cluttered dashboard.** The mass-market retail banking UI pattern (offers, upsells, 12 tiles) is the wrong register for HNW.
2. **Self-service trading UI.** Not expected; signals "retail," not "private bank."
3. **Algorithmic recommendations surfaced directly.** HNW wants the RM to mediate. AI-generated advice without RM review is a compliance and trust-model violation.
4. **Frequent authentication friction.** High security, but not 6 prompts to see a statement.
5. **Marketing content.** UHNW clients ignore marketing; they want service.
6. **Public-feeling branding.** HNW UI reads as private, restrained, and signal-of-stability.

### 1.4 The channel question — portal vs. native messaging

A major trend from [Backbase](https://www.backbase.com/blog/the-ultimate-guide-for-modern-private-banking) and [Client Window](https://www.clientwindow.com/resources/blog/client-engagement-in-finance):

- **Portals are losing.** Clients don't log in to a new app unless they must. App-fatigue is real.
- **Channel-native messaging is winning.** WhatsApp, WeChat, iMessage, SMS — the client is already there. The firm comes to them.
- **Compliance is the hard part.** WhatsApp Business API + a compliant archive (SEC 17a-4, FINRA 3110) is non-trivial. Most firms either ban it outright or partner with archival vendors.
- **HNW in APAC heavily uses WeChat.** WhatsApp dominates EU / LATAM / Africa. SMS / iMessage dominates North America.

V3's client persona surface is explicitly a **channel-native messaging** surface (WhatsApp-styled phone frame), not a portal. That's the right call per the research. It also means the feature set should stay **deliberately narrow** — mass-market portal features are not the goal.

### 1.5 Regulatory / trust boundaries for the client surface

From Reg BI (via the advisor-side research), SEC recordkeeping (Rule 17a-4), FINRA 3110 (supervision of electronic communications):

1. Every client message is a "communication with the public" — must be archived, supervisable, and reviewable.
2. No personalized investment advice from a bot without RM review. The bot can educate, acknowledge, and escalate. It cannot recommend.
3. Positions, holdings, and recommendations are MNPI-sensitive for employees and privacy-sensitive for clients — the client-facing surface must never surface unfiltered MNPI (e.g., pending research on a stock they hold).
4. Escalation path to human (RM) must be obvious and one-click.

V3's design honors these: the Liaison agent is explicitly **FAQ + escalate only**, no numbers, no recommendations, always discloses, always escapes to RM for anything non-trivial.

---

## 2. What 006 V3 already has for Eleanor

Cross-checked against `docs/v3-narrative-arc.md`, `docs/v3-demo-queries-by-narrative.md`, `frontend/src/v3/personas/ClientChannelV3.tsx`, `frontend/src/v3/atoms/ClientTraceStripV3.tsx`, and `openclaw/skills/rm_handoff/`.

### 2.1 Client capabilities currently covered

| Capability | V3 status | Evidence |
|---|---|---|
| WhatsApp-styled phone surface with green header, bubbles, composer | ✅ | `ClientChannelV3.tsx` — phone frame, 5G status bar, chat thread |
| Liaison agent answers FAQs (Haiku 4.5) | ✅ | Per arc doc §7 — faq-specialist inside liaison-orchestrator |
| Auto-generated opening "Good morning" bubble | ✅ | `ClientChannelV3.tsx` empty-state |
| Disclaimer strip ("For informational purposes. Your RM makes recommendations.") | ✅ | Yellow bar, visible always |
| Two canned CTAs — "Schedule call" and "Ask my RM" | ✅ | Pre-fills a turn for the liaison |
| MNPI filter on client turns | ✅ | Per arc doc §7 — `fsi-client-liaison` has MNPI-filtered context reads |
| RM handoff (creates `Client_Inquiry__c`) | 🟡 | Live per N2; `rm_handoff` skill exists; `Research_Request__c` metadata partial |
| Client turn audit row | 🟡 | Per v3-design-vs-built-v2 §4d — audit rows may drop silently due to missing fields |
| Queue update event (lights up RM workbench in real time) | 🟡 | WebSocket event exists; RM side broken because V3 replaced queue with placeholder |
| Client-simple traversal map (5-node horizontal spine hiding specialist churn) | ✅ | `TraversalMapV3 variant="client-simple"` |
| Client-trace strip — user-visible moments only | ✅ | `ClientTraceStripV3.tsx` — "sent · liaison replied · MNPI cleared · audit written · handed off" |
| Architecture map narration ("One trust spine. Three surfaces.") | ✅ | Hero caption below the phone |
| Audit strip at bottom | ✅ | `AuditStripV2` reused |

### 2.2 What the client surface looks like today

Reading `ClientChannelV3.tsx`:

- **Top:** PersonaHeaderV3 in `surface="channel"` (WhatsApp-green brand-locked, no theme toggle)
- **Hero row (three-column):**
  - **Left caption:** "Client surface. Channel-native, not a portal." (pitch text)
  - **Center — phone frame:** iPhone-styled, 9:41 status bar, chat header "Your Wealth Team · online", thread of bubbles, yellow disclaimer, two CTAs, composer with send arrow
  - **Right caption:** "What Eleanor sees. Just a chat." (pitch text — explicitly calls out absence of dashboards)
- **Full-width trace row:**
  - Heading: "Behind the scenes. One trust spine. Three surfaces."
  - `TraversalMapV3` in client-simple variant (5 nodes only)
  - `ClientTraceStripV3` with user-visible moments
- **Bottom:** AuditStripV2

### 2.3 What's genuinely good about this surface

- **Restraint as a design principle.** The absence of dashboards is *the point*. Zero positions, zero numbers, zero recommendations. This is aligned with HNW UX research and Reg BI.
- **Phone frame stages the pitch.** Putting the client UI inside a phone frame with pitch captions either side is a smart demo move — the panel reads "channel-native" without the demoer having to explain it.
- **MNPI-safe by construction.** The Liaison agent is architecturally incapable of leaking positions.
- **Client-simple trust visualization.** The 5-node spine replaces the research/advisor full 17-agent map; the client sees exactly the right amount of "how it works."
- **One trust spine, three surfaces** narration is the cross-persona story of V3 in one line. The client panel is where it lands hardest because the contrast with Sarah's and Marcus's complex surfaces is strongest.

### 2.4 What the current client surface is missing to feel production-complete

A private-bank product lead would notice:

1. **It's a one-shot chat.** No message history across sessions. Eleanor reloads → thread is empty.
2. **No rich messages.** Cannot render cards, links, documents, or action buttons beyond the two hardcoded CTAs.
3. **No "my RM" card.** Who is Marcus? What's his photo, his number, his last touch date? HNW clients relate to the *person*.
4. **No secure document upload.** KYC annual refresh, trust docs, ID — basic table stakes.
5. **No appointment booking confirmation.** "Schedule a call" fires a message, nothing actually gets scheduled.
6. **No proactive outbound notifications.** The arc doc promises this via Platform Events; the client surface has no inbound-push channel.
7. **No language / channel options.** HNW clients are often multilingual. No language toggle.
8. **No authentication ceremony on the client side.** The demo skips login, which is fine; but there's no biometric / 2FA signal-of-security visible.
9. **No "forward me the brief" flow.** If Eleanor wants to see the public-summary version of Sarah's NVDA brief (MNPI-stripped), there's no way to request or receive it.
10. **No portfolio summary link-out (even if we don't render positions).** "See your quarterly summary" button that opens a PDF is standard.

Critically, most of these should **not** be built into the client surface for the demo. The panel's likely concerns about the client surface are *credibility* (is this real trust enforcement) and *market fit* (does this match private-bank UX patterns), not *feature parity with Robinhood*. Restraint is correct.

---

## 3. Enhancement directions, grouped by theme

### Theme A — Make the chat feel like a real WhatsApp conversation

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| A1 | **Persistent thread** — messages survive refresh (localStorage then AgentCore memory) | "This is a real chat, not a demo" | 4 | 1 |
| A2 | **Typing indicator** while liaison is reasoning | Channel parity | 3 | 0.5 |
| A3 | **Read receipts** (✓✓ blue when RM opens) | Cross-persona handshake visible on the client side | 4 | 1 |
| A4 | **Rich message card** — render "Your RM Marcus will reach out" as a card with Marcus's avatar, last-seen, one-tap to schedule | HNW UX — the person, not the process | 4 | 1.5 |
| A5 | **Message status chips** — "queued · reviewed · resolved" on client's inquiry, updated live | Trust + progress visibility | 3 | 1 |

### Theme B — Proactive outbound (the push channel)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| B1 | **RM-initiated message** — Marcus replies from his workbench → bubble appears in Eleanor's thread in real time | Two-screen demo gold: Marcus types, Eleanor's phone updates, narrator says "one trust spine." | 5 | 2 |
| B2 | **Proactive alert** — "Your advisor has updated research on a stock in your household" (MNPI-stripped, links to sanitized summary) | Narrative 3/4 lands on the client surface, not just the advisor's | 4 | 2 |
| B3 | **Appointment confirmation card** — "Call scheduled with Marcus, Tue 2pm" after scheduling | Closes the loop on CTA #1 | 3 | 1.5 |
| B4 | **Statement / document drop** — "Your Q1 statement is ready" as a rich bubble with a download link | Every private bank does this; signals production-complete | 3 | 2 |

### Theme C — Safety rails made visible (the "trust" pitch)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| C1 | **"Why I can't answer that" bubble** — when client asks "What's my NVDA position worth?" the Liaison responds with a specific, dignified explanation that positions are an RM-channel thing, with a one-tap escalation | Reg BI / MNPI safety rail demonstrated in the client's own experience | 5 | 1.5 |
| C2 | **MNPI-stripped summary of a published brief** — when Sarah publishes NVDA brief and Eleanor has NVDA, Eleanor receives a sanitized summary with "read more in a call with Marcus" | The cross-persona story landing on the client surface | 5 | 2.5 |
| C3 | **Regulatory disclosure link** at the bottom of the thread | Standard | 1 | 0.25 |
| C4 | **Biometric prompt simulation** on sensitive intents | Signal-of-security visual | 3 | 1 |

### Theme D — Language, accessibility, and HNW polish

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| D1 | **Language toggle** (EN / zh / es / fr / ar) | HNW is global; matches Standard Chartered / HSBC patterns | 3 | 2 |
| D2 | **Voice note input** (recording button → Whisper transcript → liaison turn) | Channel-native; HNW clients are time-poor | 3 | 2.5 |
| D3 | **Bigger type, higher contrast option** | HNW demographic skews older; accessibility matters | 2 | 0.5 |
| D4 | **Private-bank brand skin** — neutral dark / ivory palette instead of WhatsApp green, as a demo mode | Shows the design decouples from the channel | 2 | 1 |

### Theme E — The "how it works" narration (V3's genuine differentiator)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| E1 | **Animated trust-spine micro-diagram** inside the trace panel — pulse flows from client icon → liaison → MNPI filter → audit, on every turn | The restraint pitch made visceral | 4 | 2 |
| E2 | **"Three personas. One runtime." comparative strip** — small thumbnails of Sarah / Marcus / Eleanor surfaces with a shared trace highlight | Makes the cross-persona story explicit on the client page | 4 | 2.5 |
| E3 | **Click-through from ClientTraceStripV3 events to the full Langfuse trace** (already partly there for other personas) | Deeper trust story for a technical panel member | 3 | 1 |
| E4 | **Audit footer — "this conversation is recorded and supervised"** | Regulatory reality shown, not hidden | 2 | 0.25 |

---

## 4. Demo-worthiness ranking

### 4.1 Tier 1 — ship for the next demo (high value, low-medium cost, story-critical)

| Rank | Feature | Why it earns the slot |
|---|---|---|
| 1 | **B1** — RM-initiated message appears in Eleanor's thread | Two-screen demo gold; closes the cross-persona loop the V3 narrative claims |
| 2 | **C1** — "Why I can't answer that" dignified refusal bubble | Single best visual of Reg BI / MNPI safety rails in action |
| 3 | **A4** — Rich RM card with Marcus's identity | HNW UX anchor; simple and impactful |
| 4 | **A1** — Persistent thread across refresh | Demo stability + channel parity |
| 5 | **C2** — MNPI-stripped brief summary delivered to Eleanor when Sarah publishes | Lands the full three-persona handshake on the client screen |

### 4.2 Tier 2 — second wave

6. B2 — Proactive alert bubble
7. E1 — Animated trust-spine micro-diagram
8. A3 — Read receipts ✓✓
9. B3 — Appointment confirmation card
10. A2 — Typing indicator

### 4.3 Tier 3 — nice-to-haves

A5, B4, C3, C4, D1, D2, D3, D4, E2, E3, E4

---

## 5. What SHOULD and SHOULD NOT go into the demo

### 5.1 Go

1. **Persistent thread** (A1) — the chat should feel real
2. **Rich RM card** (A4) — HNW clients see the person, not the process
3. **RM-initiated reply appearing in client thread** (B1) — two-screen demo closes the loop
4. **Dignified "can't answer positions" refusal** (C1) — the safety rail is the story
5. **MNPI-stripped brief summary** to Eleanor when Sarah publishes (C2) — full three-persona handshake lands here
6. **Keep the phone frame, keep the captions, keep the trace strip** — the restraint *is* the differentiation

### 5.2 Do NOT go

1. **Do not add a portfolio dashboard.** It contradicts the "channel-native not a portal" thesis AND the HNW UX research AND the MNPI trust model.
2. **Do not add self-service trading.** Signals retail, not private bank. Wrong persona.
3. **Do not add recommendations.** The bot educates and escalates; it never recommends. Reg BI boundary.
4. **Do not add 12 CTAs.** Two is right. HNW UI is restrained.
5. **Do not add marketing / cross-sell surfaces.** UHNW clients ignore them.
6. **Do not add a "Powered by AI" banner.** HNW clients want service, not technology branding.
7. **Do not skip authentication theatrically.** If the demo login is "dev-bootstrap-token" the client surface should still have a plausible biometric prompt. Visible security matters.

### 5.3 The one-slide framing

> "V3 Client Channel — an HNW client opens WhatsApp like any morning. The Liaison agent answers general questions with dignity, refuses anything that requires RM judgment, and routes real decisions to the human. When the RM replies, her thread updates in real time. When her research team publishes a brief affecting a stock she owns, a sanitized summary lands — with an invitation to discuss with her RM. Every message is supervised, every refusal is audited, every cross-persona handoff is visible. The client sees a chat. The firm sees the same seven gates."

---

## 6. Executable feature map

### 6.1 Epics

| ID | Epic | Story | Acceptance | Size (half-days) |
|---|---|---|---|---|
| E-E1 | Persistent thread | As Eleanor, my chat history survives refresh and re-login | Reload preserves thread; AgentCore user memory carries a message cap per client | 2 |
| E-E2 | Rich RM identity card | As Eleanor, when the liaison escalates I see a card with my RM's name, avatar, and a "schedule" button | Card renders; tap-to-schedule integrates with B3 | 3 |
| E-E3 | RM → client live reply | As Eleanor, when Marcus types a reply on his workbench, it appears in my thread within 2s | Two-tab test: Marcus types, Eleanor's thread updates | 4 |
| E-E4 | Dignified refusal | As Eleanor, when I ask "what's my NVDA position worth" I get a dignified bubble explaining this is an RM-channel thing, with one-tap escalation | Query matches position-intent → specific canned response + escalation CTA | 3 |
| E-E5 | MNPI-stripped brief summary | As Eleanor, when Sarah publishes a brief on a ticker in my household, I receive a sanitized 2-sentence summary + "discuss with Marcus" CTA | Brief publish → event → matching household → sanitized message delivered | 5 |
| E-E6 | Typing indicator + read receipts | As Eleanor, I see typing dots during liaison reasoning, and ✓✓ when Marcus reads | Indicators render; ✓✓ fires on Marcus-tab focus event | 3 |
| E-E7 | Appointment confirmation card | As Eleanor, after tapping "Schedule call" I receive a rich card confirming the slot | Scheduling stub (hardcoded slot OK for demo); card renders | 3 |
| E-E8 | Proactive alert bubble | As Eleanor, when an alert fires from compliance_sweep on a held stock, I receive a gentle, non-alarmist bubble | Alert event → matching household → bubble delivered with RM CTA | 4 |

**Total:** 27 half-days = 13.5 build-days across E-E1 through E-E8. Tier 1 only (E-E1 through E-E5) is ~17 half-days = 8.5 days.

### 6.2 Sequencing

Suggested execution order (~2 calendar weeks for one engineer):

```
Day 1–2     (E-E1)   persistent thread — foundation
Day 3–4     (E-E2)   rich RM card
Day 5–6     (E-E4)   dignified refusal — trust story
Day 7–8     (E-E3)   RM → client live reply — demo hero
Day 9–10    (E-E5)   MNPI-stripped brief summary — three-persona loop
[Tier 1 demo-ready checkpoint — 8.5 days]
Day 11–12   (E-E6)   typing + read receipts
Day 13–14   (E-E7)   appointment confirmation
Day 15–16   (E-E8)   proactive alert bubble
```

### 6.3 What breaks if we do NOTHING

- The client surface is the strongest thing in V3 demos today — restraint-as-feature is genuine differentiation. Doing nothing holds ground, but:
- Narrative 2's RM-notifies-client loop is visibly incomplete (Marcus has no way to reply into the thread live).
- Narrative 3 (compliance alert → affected clients) has no client-side delivery surface; it exists on Marcus's workbench only.
- The "three personas, one runtime" story stops one hop short of the client screen.
- First-time demo viewers may mistake restraint for emptiness unless the trust-rail moments (C1, C2) are present.

### 6.4 What's intentionally out of scope

- Portfolio dashboards (violates channel-native pitch + HNW UX + MNPI model)
- Self-service trading (wrong persona)
- Recommendations without RM review (Reg BI boundary)
- Multi-channel delivery (actual WhatsApp Business API wiring) — the simulated channel is fine for demo; real channel is productionization
- Rich media beyond cards (video, voice notes, location) — nice but not story-critical
- Third-party integrations (Plaid, aggregators) — wrong scope

---

## 7. Summary

The V3 client channel has the **strongest design restraint of any persona** — a phone frame with two CTAs, a disclaimer, and a trust-spine narration. That restraint IS the differentiation. The things missing are not "features to add" in the retail-banking sense; they are three specific trust-story moments that complete the cross-persona loop:

1. **Marcus replying into Eleanor's thread live** (B1/E-E3) — closes the RM→client direction
2. **Eleanor receiving a dignified refusal** when she asks for positions (C1/E-E4) — the safety rail visible
3. **Eleanor receiving a sanitized brief summary** when Sarah publishes (C2/E-E5) — the three-persona handshake lands on the client screen

Add persistent thread (E-E1) and a rich RM card (E-E2) for production feel, and the Tier 1 scope is 8.5 build-days. After that, everything else is bonus polish, not story-critical.

The Principal-level bet on this persona: the panel is not evaluating whether the agent can chat. They are evaluating whether the agent can be trusted in the client's hand. That is shown by what the agent *won't* say, not what it will. The dignified refusal is the single most important feature on this surface — more important than any affirmative capability.

---

## 8. References

HNW / private-bank client experience:
- [Backbase — Private Banking Modern Digital Guide](https://www.backbase.com/blog/the-ultimate-guide-for-modern-private-banking)
- [Cutter Associates — Evolution of Wealth Management Client Experience](https://www.cutterassociates.com/insights/the-evolution-of-the-wealth-management-client-experience)
- [BeckDigital — UX for HNW Wealth Management](https://beckdigital.com/insights/ux-for-high-net-worth-wealth-management/)
- [Wealth Management — UHNW Advisors Losing the Digital Race](https://www.wealthmanagement.com/high-net-worth/uhnw-advisors-are-losing-the-digital-race)
- [Finantrix — Wealth Management Platforms Buyer's Guide](https://www.finantrix.com/buyer-guides/wealth-management-platforms-private-banks)
- [Finantrix — Private Banking Solutions for Affluent Clients](https://www.finantrix.com/buyer-guides/private-banking-solutions-affluent-clients)

Private-bank mobile / channel reference:
- [J.P. Morgan Mobile for Private Bank](https://privatebank.jpmorgan.com/gl/en/about-us/jp-morgan-mobile-app)
- [Standard Chartered Private Bank App](https://www.sc.com/en/wealth-retail-banking/private-banking/private-bank-app/)
- [Barclays Private Bank App](https://privatebank.barclays.com/digital-banking/the-barclays-app/)
- [RMB Private Bank — Secure Chat in Service Suite](https://www.rmbprivatebank.com/ways-to-bank/digital/messaging.html)

Messaging / channel-native:
- [Client Window — WhatsApp API in Wealth Management](https://www.clientwindow.com/resources/blog/client-engagement-in-finance)
- [Vonage — Omnichannel Client Account Updates](https://www.vonage.com/resources/articles/automated-messaging/)
- [Windmill — Digital Private Banking Platform](https://windmill.digital/work/omni-channel-platform-for-private-banking/)
- [Trust and Digital Privacy — Banking Chatbots Study (NIH)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9035985/)

V3 internal references:
- `docs/v3-narrative-arc.md` (esp. §7 client-liaison persona)
- `docs/v3-demo-queries-by-narrative.md` (N2 client-drives-research)
- `docs/v3-design-vs-built-vs-deployed-v2.md`
- `frontend/src/v3/personas/ClientChannelV3.tsx`
- `frontend/src/v3/atoms/ClientTraceStripV3.tsx`
- `frontend/src/v3/atoms/TraversalMapV3.tsx` (`variant="client-simple"`)
- `openclaw/skills/rm_handoff/`, `openclaw/skills/compliance_sweep/`

Content was rephrased for compliance with licensing restrictions.

# 006 V3 Client (End-Investor) — What's There vs What's Not

> **Date:** 2026-05-01
> **Companion to:** `v3-client-feature-map.md`
> **Purpose:** at-a-glance table for the `fsi-client-liaison` persona (Eleanor Vance).
>
> Legend: ✅ live, 🟡 partial/broken, ❌ not built. P0 = ship for next demo, P1 = second wave, P2 = depth, P3 = nice-to-have. *Note: unlike Research and Advisor, the Client persona is deliberately minimal — absence of features is a design decision, not a gap.*

---

## Table 1 — Client capabilities (what Eleanor can do)

| # | Capability | There? | State | Priority |
|---|---|---|---|---|
| 1 | Send a message via WhatsApp-styled composer | ✅ | Works, streaming reply | — |
| 2 | Receive FAQ answers from Haiku liaison | ✅ | Live, ~5s for FAQ tier | — |
| 3 | Two canned CTAs — "Schedule call", "Ask my RM" | ✅ | Pre-fill a turn | — |
| 4 | Auto opening "Good morning" bubble | ✅ | Empty-state greeting | — |
| 5 | MNPI filter on all responses (no positions, no numbers) | ✅ | Architectural; liaison allowlist blocks it | — |
| 6 | Always-visible disclaimer ("Your RM makes recommendations") | ✅ | Yellow bar | — |
| 7 | RM handoff creates `Client_Inquiry__c` | ✅ | Narrative 2 live | — |
| 8 | Queue update fires to RM workbench | 🟡 | Event fires but RM queue column regressed to placeholder | **P0** — shared with advisor fix |
| 9 | Audit row per client turn | 🟡 | May silently drop fields | **P0** — shared with advisor |
| 10 | Persistent thread across refresh | ❌ | Thread is in-memory only | **P0** |
| 11 | RM replies appear in client thread live | ❌ | Not built | **P0** — demo hero |
| 12 | Dignified refusal for position questions | ❌ | Currently generic response | **P0** — biggest trust story |
| 13 | MNPI-stripped brief summary delivered on publish | ❌ | Not built | **P0** — lands three-persona loop |
| 14 | Typing indicator during liaison reasoning | ❌ | Not built | **P1** |
| 15 | Read receipts (✓✓ blue when RM opens) | ❌ | Not built | **P1** |
| 16 | Message status chips ("queued · reviewed · resolved") | ❌ | Not built | **P2** |
| 17 | Proactive alert bubble (Narrative 3 on client surface) | ❌ | Not built | **P1** |
| 18 | Appointment confirmation card after "Schedule call" | ❌ | Not built | **P1** |
| 19 | Statement / document push bubble | ❌ | Not built | **P2** |
| 20 | Secure document upload | ❌ | Not built | **P3** |
| 21 | Voice note input (STT → liaison turn) | ❌ | Not built | **P3** |
| 22 | Language toggle (EN / zh / es / fr / ar) | ❌ | Not built | **P3** |
| 23 | Biometric prompt simulation | ❌ | Not built | **P3** |
| 24 | Accessibility mode (larger type, higher contrast) | ❌ | Not built | **P3** |
| 25 | Portfolio dashboard | ❌ | **INTENTIONALLY OUT OF SCOPE** | **Never** — violates MNPI + channel-native pitch |
| 26 | Self-service trading | ❌ | **INTENTIONALLY OUT OF SCOPE** | **Never** — wrong persona |
| 27 | AI-generated recommendations | ❌ | **INTENTIONALLY OUT OF SCOPE** | **Never** — Reg BI boundary |

---

## Table 2 — UI surfaces (what Eleanor sees on screen)

| # | Surface | There? | State | Priority |
|---|---|---|---|---|
| 1 | PersonaHeaderV3 `surface="channel"` (WhatsApp green, brand-locked) | ✅ | Rendered, no theme toggle | — |
| 2 | Phone frame with iPhone status bar (9:41 · 5G · 96%) | ✅ | Stages the pitch | — |
| 3 | Left hero caption ("Channel-native, not a portal.") | ✅ | Pitch text | — |
| 4 | Right hero caption ("Just a chat.") | ✅ | Pitch text | — |
| 5 | Chat thread with in/out bubbles + timestamps | ✅ | Works | — |
| 6 | Composer with send arrow | ✅ | Works | — |
| 7 | Yellow disclaimer strip | ✅ | Always visible | — |
| 8 | Two CTAs — Schedule call / Ask my RM | ✅ | Works | — |
| 9 | Full-width trace row ("One trust spine. Three surfaces.") | ✅ | Caption + map + strip | — |
| 10 | Client-simple traversal map (5-node spine) | ✅ | `TraversalMapV3 variant="client-simple"` | — |
| 11 | ClientTraceStripV3 (user-visible moments only) | ✅ | sent · liaison replied · MNPI cleared · audit written · handed off | — |
| 12 | Audit strip at bottom | ✅ | `AuditStripV2` reused | — |
| 13 | Rich RM identity card (Marcus avatar + name + schedule CTA) | ❌ | Not built | **P0** |
| 14 | Inbound RM message bubble (live from Marcus's workbench) | ❌ | Not built | **P0** — demo hero |
| 15 | Refusal bubble specific to position-intent queries | ❌ | Not built | **P0** |
| 16 | Brief-summary delivery bubble (MNPI-stripped) | ❌ | Not built | **P0** |
| 17 | Typing indicator dots | ❌ | Not built | **P1** |
| 18 | ✓✓ blue read receipts on client's outgoing messages | ❌ | Not built | **P1** |
| 19 | Appointment confirmation card | ❌ | Not built | **P1** |
| 20 | Proactive alert bubble (compliance or research) | ❌ | Not built | **P1** |
| 21 | Document/statement push card | ❌ | Not built | **P2** |
| 22 | Animated trust-spine micro-diagram in trace panel | ❌ | Not built | **P2** |
| 23 | Three-persona thumbnail strip (Sarah/Marcus/Eleanor shared trace) | ❌ | Not built | **P2** |
| 24 | Language toggle | ❌ | Not built | **P3** |
| 25 | Voice note input button | ❌ | Not built | **P3** |
| 26 | Biometric prompt overlay | ❌ | Not built | **P3** |
| 27 | Private-bank alternate brand skin (neutral palette) | ❌ | Not built | **P3** |
| 28 | Portfolio tiles / balance widgets | ❌ | **INTENTIONALLY ABSENT** | **Never** |
| 29 | Cross-sell / marketing tiles | ❌ | **INTENTIONALLY ABSENT** | **Never** |
| 30 | "Powered by AI" banner | ❌ | **INTENTIONALLY ABSENT** | **Never** |

---

## Table 3 — Consolidated priority map (ship in this order)

| Rank | Item | Refs | Build cost | Why it earns the slot |
|---|---|---|---|---|
| **P0-0** | Fix `queue_update` delivery (Marcus regression blocks it too) | T1 #8 | shared | Narrative 2 doesn't close without Marcus's queue |
| **P0-0** | Fix audit field drops | T1 #9 | shared | Trust spine integrity |
| **P0-1** | Persistent thread across refresh | T1 #10 | 2 days | Foundation — every other feature assumes this |
| **P0-2** | RM replies appear in client thread live | T1 #11, T2 #14 | 4 days | Two-screen demo hero; closes RM→client direction |
| **P0-3** | Dignified refusal for position questions | T1 #12, T2 #15 | 3 days | Single biggest trust-story visual; Reg BI + MNPI in action |
| **P0-4** | MNPI-stripped brief summary on publish | T1 #13, T2 #16 | 5 days | Completes three-persona handshake on the client screen |
| **P0-5** | Rich RM identity card (Marcus avatar/name/schedule) | T2 #13 | 3 days | HNW UX — the person, not the process |
| **P1-1** | Typing indicator + read receipts | T1 #14, #15, T2 #17, #18 | 3 days | Channel parity |
| **P1-2** | Appointment confirmation card | T1 #18, T2 #19 | 3 days | Closes the Schedule CTA loop |
| **P1-3** | Proactive alert bubble (Narrative 3 on client) | T1 #17, T2 #20 | 4 days | Narrative 3 lands on client surface |
| **P2** | Message status chips, document push, animated micro-diagram, three-persona strip | T1 #16, #19, T2 #21–23 | 6+ days | Polish |
| **P3** | Document upload, voice notes, language toggle, biometric, a11y, alternate brand skin | T1 #20–24, T2 #24–27 | 10+ days | Nice-to-have |
| **NEVER** | Portfolio dashboard, self-service trading, AI recommendations, marketing tiles, "Powered by AI" banner | T1 #25–27, T2 #28–30 | — | Violates channel-native pitch, HNW UX, Reg BI, or MNPI model |

---

## The one-line read

**What's there:** a deliberately restrained WhatsApp-framed surface with two CTAs, a disclaimer, MNPI-safe liaison, and a client-simple trust-spine trace. The absence of dashboards is the *design*, not a gap. V3 does this better than any other persona.

**What's missing:** three specific trust-story moments that complete the cross-persona loop — Marcus replying live into the thread (P0-2), a dignified refusal when Eleanor asks for positions (P0-3), and a sanitized brief summary when Sarah publishes (P0-4). Plus persistent thread (P0-1) and a rich RM card (P0-5) for production feel.

**Ship P0-1 through P0-5 (17 half-days = 8.5 build-days).** The client persona doesn't need more features — it needs the three trust-story moments that close the narrative loop. Everything beyond Tier 1 is optional polish.

**Single biggest unlock:** **P0-3 — the dignified refusal.** When Eleanor asks "what's my NVDA position worth?" and the liaison responds with a specific, respectful explanation that positions require the RM channel, that is the best single visual of Reg BI / MNPI safety rails in V3. More important than any affirmative feature on this surface.

---

## Cross-persona priority rollup

For the next demo push, the three at-a-glance docs combine into this joint P0 list:

| # | Item | Persona | Build cost |
|---|---|---|---|
| 1 | Fix `Published_At__c = null` on publish | Research + Advisor | 1 day (shared) |
| 2 | Add missing audit stitching fields | All three | 0.5 days (shared) |
| 3 | Restore V2 Actions queue to V3 | Advisor | 0.5 days |
| 4 | Restore V2 Client 360 to V3 | Advisor | 0.5 days |
| 5 | Coverage list rail | Research | 2 days |
| 6 | Draft → Publish button | Research | 3 days |
| 7 | Specialist gantt | Research | 2.5 days |
| 8 | Financial statement grid | Research | 3 days |
| 9 | IPS allocation bar | Advisor | 2 days |
| 10 | Client list rail | Advisor | 2 days |
| 11 | Drift dashboard | Advisor | 2.5 days |
| 12 | "Who's impacted" on brief arrival | Advisor | 2.5 days |
| 13 | Persistent client thread | Client | 2 days |
| 14 | RM→client live reply | Client | 4 days |
| 15 | Dignified refusal | Client | 3 days |
| 16 | MNPI-stripped brief summary | Client | 5 days |
| 17 | Rich RM identity card | Client | 3 days |

**Total P0 across all three personas:** ~39 build-days (~8 weeks for one engineer, ~4 weeks for two parallel engineers).

Tier-1 demo-ready scope (ship the 4 research + 5 advisor + 5 client P0s) is the cleanest story from the panel's perspective. The three persona surfaces each gain 4–5 distinct, credibility-advancing capabilities, and the cross-persona loop (brief publish → RM impact-sees → client sanitized summary; client inquiry → RM queue → RM handles → client sees reply) lights up end-to-end for the first time.

---

## Companion docs

- `v3-client-feature-map.md` — full stories, acceptance criteria, HNW UX research, citations
- `v3-research-analyst-feature-map.md` + `v3-research-analyst-there-vs-not.md` — Sarah
- `v3-advisor-feature-map.md` + `v3-advisor-there-vs-not.md` — Marcus
- `v3-narrative-arc.md` — the V3 story
- `v3-design-vs-built-vs-deployed-v2.md` — current live stack reality

# 006 V3 Advisor (RM) — What's There vs What's Not

> **Date:** 2026-05-01
> **Companion to:** `v3-advisor-feature-map.md`
> **Purpose:** the at-a-glance table a panel can read in 60 seconds for the `fsi-advisor` persona (Marcus Kerrigan).
>
> Legend: ✅ live, 🟡 partial/broken/regressed, ❌ not built. P0 = regression fixes + Tier-1, P1 = second wave, P2 = depth, P3 = nice-to-have.

---

## Table 1 — Functional capabilities (what Marcus can do)

| # | Capability | There? | State | Priority |
|---|---|---|---|---|
| 1 | Trade draft → 7-gate approval (HITL + dual-auth path) | ✅ | Code live; Narrative 5 runs in draft mode | — |
| 2 | Compliance / restricted-list screen | ✅ | Live via `compliance_screening` | — |
| 3 | Free-text conversation with `action_specialist` | ✅ | Streaming text + reply textarea works | — |
| 4 | Optimistic approval with rollback | ✅ | `useOptimisticApproval` hook | — |
| 5 | Progressive-disclosure 7-gate tracker | ✅ | Renders only when plan in flight | — |
| 6 | Architecture map with gate-chain highlight | ✅ | `TraversalMapV3 gateChainVisible` | — |
| 7 | Audit row on every outcome | 🟡 | 3 stitching fields missing from SObject — silent drops | **P0** — add `Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c` |
| 8 | Research brief awareness (reading Sarah's brief) | 🟡 | Skill exists; `Published_At__c=null` breaks Platform Event | **P0** — fix in Draft→Publish flow |
| 9 | Portfolio analytics (drift, concentration, scenarios) | 🟡 | Skill code exists, zero UI surface | **P1** — surface as drift dashboard |
| 10 | Suitability / Reg BI check | 🟡 | Skill runs, produces no visible artifact | **P1** — memo card in gate path |
| 11 | Client summary | 🟡 | Skill exists; V3 UI stubbed as "V3.1 roadmap" | **P0** — port V2 Client 360 |
| 12 | Actions queue (liaison handoffs) | 🟡 | V2 had it; V3 regressed to placeholder text | **P0** — port V2 queue |
| 13 | Live trade execution via MuleSoft | 🟡 | Code complete; CloudHub deploy never ran | **P1** — `mvn deploy -Pcloudhub-sandbox` |
| 14 | Client 360 — positions table | ❌ | Not built | **P1** |
| 15 | IPS allocation bar + concentration warnings | ❌ | Explicitly deferred in V3 comments | **P0** — unblocks Narrative 3 |
| 16 | Per-client drift / breach detection | ❌ | Not built | **P0** |
| 17 | "Who's impacted" by a new brief | ❌ | Not built | **P0** — best cross-persona story |
| 18 | Morning brief / proactive summary card | ❌ | Not built | **P1** |
| 19 | Meeting prep / review-deck draft | ❌ | Not built | **P2** |
| 20 | Post-call documentation draft | ❌ | Not built | **P2** |
| 21 | Rebalancing wizard / model-portfolio diff | ❌ | Not built | **P2** |
| 22 | Hypothetical trade impact panel | ❌ | Not built | **P2** |
| 23 | Household tree (primary + joint + trust + minor) | ❌ | Not built | **P3** |
| 24 | Per-client activity timeline | ❌ | Not built | **P2** |
| 25 | Tax-lot view | ❌ | Not built | **P3** |
| 26 | Book-level heatmap (AUM, risk, concentration) | ❌ | Not built | **P3** |
| 27 | Salesforce FSC Action Plans surface | ❌ | Not built | **P3** |
| 28 | Dual-auth approver inbox (senior compliance) | ❌ | Not built | **P2** |
| 29 | Execution confirmation card (post-MuleSoft receipt) | ❌ | Not built | **P2** — depends on #13 |
| 30 | Client alert queue (Narrative 3) | ❌ | Not built | **P2** |
| 31 | Outreach drafting (per-client personalization) | ❌ | Not built | **P2** — depends on #17 |

---

## Table 2 — UI surfaces (what Marcus sees on screen)

| # | Surface | There? | State | Priority |
|---|---|---|---|---|
| 1 | PersonaHeaderV3 (SLDS light theme, Cognito sign-out) | ✅ | Rendered | — |
| 2 | 7-gate tracker with progressive disclosure | ✅ | Renders when plan in flight | — |
| 3 | Center Conversation column with streaming text | ✅ | Works | — |
| 4 | Inline `InlineActionCard` HITL approval inside chat | ✅ | Works; Cmd-Enter approves | — |
| 5 | Reply textarea with Cmd-Enter submit | ✅ | Works | — |
| 6 | Architecture map (live traversal) | ✅ | Collapsible panel; nodes pulse | — |
| 7 | End-to-end trace collapsible | ✅ | Langfuse deep-link | — |
| 8 | Audit strip bottom (correlation_id, gates, latencies) | ✅ | Works | — |
| 9 | Left Actions column | 🟡 | Placeholder "V3.1 roadmap" — **regression from V2** | **P0** — port V2 queue |
| 10 | Right Client 360 column | 🟡 | Placeholder "V3.1 roadmap" — **regression from V2** | **P0** — port V2 Client 360 |
| 11 | Client list / book rail | ❌ | Not built | **P0** |
| 12 | IPS allocation bar with breach chips | ❌ | Not built | **P0** |
| 13 | Drift dashboard across the book | ❌ | Not built | **P0** |
| 14 | "Who's impacted by this brief" list | ❌ | Not built | **P0** |
| 15 | Suitability memo card inside gate path | ❌ | Not built | **P1** |
| 16 | Morning brief card on workbench open | ❌ | Not built | **P1** |
| 17 | Positions table | ❌ | Not built | **P1** |
| 18 | Per-client activity timeline | ❌ | Not built | **P2** |
| 19 | Goals / objectives display | ❌ | Not built | **P3** |
| 20 | Scenario-modeling output panel | ❌ | Not built | **P2** |
| 21 | Hypothetical trade impact pane | ❌ | Not built | **P2** |
| 22 | Execution confirmation card | ❌ | Not built | **P2** |
| 23 | Dual-auth approver inbox | ❌ | Not built | **P2** |
| 24 | Book-level heatmap (concentration across book) | ❌ | Not built | **P3** |
| 25 | Household tree view | ❌ | Not built | **P3** |
| 26 | FSC Action Plans surface | ❌ | Not built | **P3** |
| 27 | Upcoming reviews / birthdays rail | ❌ | Not built | **P3** |

---

## Table 3 — Consolidated priority map (ship in this order)

| Rank | Item | Refs | Build cost | Why it earns the slot |
|---|---|---|---|---|
| **P0-0** | Restore V2 Actions queue to V3 | T1 #12, T2 #9 | 0.5 days | Fix the regression before anything else |
| **P0-0** | Restore V2 Client 360 to V3 | T1 #11, T2 #10 | 0.5 days | Fix the regression |
| **P0-0** | Add missing audit stitching fields | T1 #7 | 0.5 days | Trust spine silent holes; blocks every narrative's audit claim |
| **P0-0** | Fix `Published_At__c = null` on brief publish | T1 #8 | shared w/ Sarah | Platform Event to RM queue never fires without this |
| **P0-1** | "Who's impacted" cross-reference on new brief | T1 #17, T2 #14 | 2.5 days | Best cross-persona story; one click from Sarah → RM action |
| **P0-2** | IPS allocation bar + concentration chips | T1 #15, T2 #12 | 2 days | Unblocks Narrative 3; explicitly deferred in V3 code |
| **P0-3** | Client list rail | T2 #11 | 2 days | RM has a book; workstation feel |
| **P0-4** | Drift dashboard | T1 #16, T2 #13 | 2.5 days | Proactive monitoring on screen |
| **P1-1** | Suitability memo card inside gate path | T1 #10, T2 #15 | 2 days | Reg BI documentation visibly produced |
| **P1-2** | Morning brief card on open | T2 #16 | 2.5 days | First-impression hero |
| **P1-3** | Positions table in Client 360 | T1 #14, T2 #17 | 1.5 days | Table stakes |
| **P1-4** | Deploy MuleSoft to CloudHub | T1 #13 | 2 days | Narrative 5 goes from draft-only to live |
| **P2** | Scenario modeling UI, hypothetical trade impact, execution confirmation, dual-auth inbox, client alert queue, outreach drafting, activity timeline, meeting prep, post-call docs, rebalancing wizard | T1 #9, #19–22, #24, #28–31, T2 #18, #20–23 | 20+ days | Deepens the story |
| **P3** | Household tree, tax lots, book heatmap, FSC Action Plans, reviews rail, goals | T1 #23, #25–27, T2 #19, #24–27 | 10+ days | Nice-to-have |

---

## The one-line read

**What's there:** a strong trust spine (7 gates, HITL card, optimistic approval, dual-auth). The trade-approval surface is the best thing in V3.

**What's missing:** almost every pre-trade part of an RM's day. V3 regressed the Actions queue and Client 360 to placeholders ("V3.1 roadmap"). No book view, no IPS bar, no drift, no "who's impacted", no morning brief.

**Ship P0-0 × 4 (2 days) + P0-1 through P0-4 (9 days) = 11 build-days.** That turns the demo from "impressive trade approval with seven gates" into "an actual wealth advisor workbench with the agents inside it."

---

## Companion docs

- `v3-advisor-feature-map.md` — full stories, acceptance criteria, industry research, citations
- `v3-research-analyst-feature-map.md` — companion for Sarah
- `v3-research-analyst-there-vs-not.md` — companion at-a-glance for Sarah
- `v3-narrative-arc.md` — the V3 story
- `v3-design-vs-built-vs-deployed-v2.md` — current live stack reality
- `v3-live-traversal-ui-design.md` — specialist gantt / architecture map design

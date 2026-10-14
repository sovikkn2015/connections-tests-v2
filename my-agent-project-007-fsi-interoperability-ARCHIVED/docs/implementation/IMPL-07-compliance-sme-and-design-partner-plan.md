# IMPL-07: Compliance SME Hiring and Design Partner Identification

> Date: April 14, 2026
> Category: IMPLEMENTATION (how to build)
> Purpose: Actionable plan for the two non-technical blockers: compliance SME and design partner

---

## ITEM 6: COMPLIANCE SME HIRING

### Why This Is Critical Path

Every LLMJ reviewer flagged this. The compliance SME blocks:
- M3 canonical schema (18 types need semantic validation)
- M2/M4 OPA rules (2,100+ lines of Rego need regulatory validation)
- Reg BI documentation generator (conflict inventory, suitability methodology)
- BSA/AML thresholds (SAR triggers, CTR filing format)
- ERISA account-type rules (prohibited transactions, plan constraints)
- WSP-to-YAML mapping (human-readable supervisory procedures)
- Principal review queue design (FINRA 2210 requirements)

### Profile

- FINRA Rule 3110/3120 experience (supervisory procedures)
- Reg BI implementation experience (Care, Disclosure, Conflict, Compliance obligations)
- Ability to translate regulatory requirements to machine-readable rules
- Familiarity with OPA/Rego is a plus but not required (architect translates)
- Part-time contract: 20 hrs/week Phase 0-1, 15 hrs/week Phase 2+
- Rate: $200-400/hr. Budget: $15-25K Phase 0, $72K Phase 1, $72K Phase 2.

### Where to Find

1. Compliance consulting firms: Oyster Consulting, RIA in a Box, XY Planning Network
2. Former FINRA examiners (now in private practice)
3. CCOs at mid-size BDs who do consulting on the side
4. LinkedIn: "FINRA compliance consultant" + "Reg BI" + "supervisory procedures"
5. Industry conferences: SIFMA Compliance & Legal, NSCP National Conference

### Hiring Timeline

- Week 0: Post job description, reach out to 3 candidates
- Week 1: Interview top 2, check references
- Week 1-2: Engage, sign contract, NDA
- Week 2: Onboarding — review ARCH-06, ARCH-03, M3 schema stubs
- Week 3-4: Begin M3 schema co-design and M2/M4 rule validation

### Acceptance Criteria

SME is onboarded when they can:
1. Review a canonical type definition and identify missing fields or incorrect semantics
2. Write a WSP section that maps to an OPA/Rego rule
3. Validate a Reg BI document template against SEC Rule 15l-1
4. Define SAR trigger thresholds appropriate for the firm's risk profile

---

## ITEM 7: DESIGN PARTNER IDENTIFICATION

### Why This Is Critical Path

Zero customers is the existential risk (LLMJ Reviewer 5, score 4/10 on time-to-market). The wedge product (Compliance Proxy for MCP) ships Week 14-18 but needs a design partner to validate with real data. The Phase 2 lighthouse (Week 28-36) needs 3-5 RIA firms committed.

### Target Profile: Tier 4 Independent RIA

- AUM: $100M-$1B (large enough to have real complexity, small enough to move fast)
- Tech stack: Salesforce FSC + Orion + Schwab (our Phase 2 adapters)
- Team: 5-50 advisors (enough users for meaningful feedback)
- Pain: spending significant time on manual data entry and meeting prep
- Willingness: to use "draft mode" agent and provide feedback
- Timeline: can commit to 3-month pilot starting Month 8

### Where to Find

1. RIA custodian conferences: Schwab IMPACT, Fidelity Inside Track
2. Wealthtech conferences: T3 Technology Conference, WealthStack Solutions
3. Industry associations: NAPFA (fee-only advisors), FPA (financial planners)
4. Orion user community (Orion Ascent conference)
5. LinkedIn outreach to RIA founders/COOs who post about tech frustration
6. Referrals from compliance SME (they know firms struggling with integration)

### Outreach Plan

- Week 1-2: Identify 15-20 candidate firms from conference attendee lists and LinkedIn
- Week 2-3: Send personalized outreach (not cold email — reference specific pain points)
- Week 3-4: Demo the architecture (not the product — it doesn't exist yet). Show the call flow diagram. Explain "draft mode."
- Week 4: Secure 3-5 verbal commitments or LOIs for pilot program
- Month 4 (Phase 1 end): Demo wedge product (Compliance Proxy for MCP) to committed partners
- Month 8 (Phase 2): Deploy lighthouse to 3-5 partners

### What We Offer Design Partners

- Free access during pilot (3-6 months)
- Direct input on feature prioritization
- Compliance SME consultation (shared benefit)
- Early access to production platform at discounted rate
- Co-marketing opportunity (case study, conference presentation)

### What We Need From Design Partners

- Access to Salesforce FSC sandbox with real (anonymized) data
- Access to Orion sandbox or API credentials
- 2-3 advisors willing to use the agent daily for 4+ weeks
- Weekly feedback sessions (30 min)
- Permission to track edit rates and usage patterns
- Willingness to be a reference customer

### Success Criteria

By end of Phase 0 (Week 4):
- 3-5 RIA firms identified with verbal commitment
- At least 1 firm with Salesforce FSC + Orion + Schwab stack
- At least 1 firm willing to provide sandbox access

By end of Phase 1 (Week 18):
- Wedge product demoed to all committed partners
- At least 1 firm testing Compliance Proxy for MCP with real MCP traffic

By end of Phase 2 (Week 36):
- 3-5 firms using full agent in draft mode daily
- Edit rate tracking operational
- Feedback incorporated into schema revisions

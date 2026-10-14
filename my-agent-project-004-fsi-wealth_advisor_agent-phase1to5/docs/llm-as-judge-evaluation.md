# LLM-as-Judge Evaluation Framework

## WA_P1to5_Advisor Agent — Comprehensive Quality Evaluation

This document defines how to use an LLM (GPT-4, Claude, etc.) as an automated judge to evaluate the quality of the WA_P1to5_Advisor agent's responses beyond simple topic/action matching. Salesforce's `bot_response_rating` expectation in the AI Evaluation Definition uses LLM-as-Judge under the hood — this doc provides the rubrics, golden answers, and scoring criteria that feed into that evaluation.

---

## Table of Contents

1. [Evaluation Dimensions (Rubrics)](#1-evaluation-dimensions-rubrics)
2. [Golden Answers — All 32 Test Cases](#2-golden-answers--all-32-test-cases)
3. [LLM Judge Prompt Template](#3-llm-judge-prompt-template)
4. [Scoring Thresholds](#4-scoring-thresholds)
5. [Batch Evaluation Script](#5-batch-evaluation-script)
6. [Salesforce-Specific: bot_response_rating](#6-salesforce-specific-bot_response_rating)
7. [Evaluation Results Template](#7-evaluation-results-template)

---

## 1. Evaluation Dimensions (Rubrics)

Each agent response is scored on 6 dimensions, each rated 1–5.

### A. Data Accuracy (1–5)

Does the response contain correct data from the seed data? Are dollar amounts, percentages, names, and dates accurate?

| Score | Criteria |
|-------|----------|
| 5 | All data points match seed data exactly (names, amounts, percentages, dates) |
| 4 | All key data correct, one minor formatting difference (e.g., $2.8M vs $2,800,000) |
| 3 | Most data correct, 1–2 minor discrepancies (e.g., rounding differences) |
| 2 | Several data errors or one major error (wrong account balance, wrong client) |
| 1 | Major data errors, fabricated data, or data from the wrong client/household |

### B. Completeness (1–5)

Does the response include all relevant information for the action type?

| Action | Required Fields for Score 5 |
|--------|-----------------------------|
| `client_lookup` | Household name, Total AUM, Risk Profile, Advisor, all Members (name, role, email), all Accounts (name, type, balance) |
| `portfolio_review` | Client name, Household, Risk Profile, all Accounts (name, type, balance, allocation, YTD return), Total Portfolio Value |
| `goal_planning` | All goals (name, target amount, current amount, progress %, gap, target date) |
| `meeting_prep` | Client info, household, AUM, risk profile, meeting details (subject, date, location, notes, action items), portfolio snapshot, goals status, talking points |
| `rebalancing` | Risk profile, target allocation, per-account current allocation, drift per component, drift flags, overall recommendation |
| `transactions` | Up to last 10 transactions (date, type, amount, symbol, description), summary totals (buys, sells, dividends, fees, net) |
| `compliance` | Risk profile, target allocation, per-account checks (suitability, concentration, drift), pass/fail, violations list |
| `referrals` | Referral name, source, type, date, status, estimated value, summary totals |

| Score | Criteria |
|-------|----------|
| 5 | All expected fields present and populated |
| 4 | All key fields present, 1 minor field missing (e.g., email on client lookup) |
| 3 | Key fields present but some secondary fields missing |
| 2 | Several important fields missing |
| 1 | Most fields missing or response is a stub |

### C. Relevance (1–5)

Is the response on-topic for the user's question?

| Score | Criteria |
|-------|----------|
| 5 | Directly answers the question with no unnecessary tangents |
| 4 | Answers the question with minor additional context that's still useful |
| 3 | Answers but includes irrelevant information or partially addresses the question |
| 2 | Partially on-topic but misses the core question |
| 1 | Off-topic, doesn't address the question, or answers a different question entirely |

### D. Tone & Professionalism (1–5)

Is the response appropriate for a wealth advisor context?

| Score | Criteria |
|-------|----------|
| 5 | Professional, clear, well-structured, advisor-appropriate language |
| 4 | Professional with minor formatting issues |
| 3 | Acceptable but could be more polished or better organized |
| 2 | Somewhat unprofessional, confusing structure, or overly casual |
| 1 | Unprofessional, confusing, inappropriate, or contains jargon errors |

### E. Actionability (1–5)

Does the response give the advisor something they can act on?

| Score | Criteria |
|-------|----------|
| 5 | Clear next steps, actionable insights, or decision-ready data |
| 4 | Good actionable info with minor gaps |
| 3 | Some actionable information but vague or requires further analysis |
| 2 | Limited actionable content |
| 1 | No actionable information — just raw data dump or generic text |

**Action-specific actionability criteria:**
- **meeting_prep**: Are talking points specific and useful? Do they reference actual portfolio/goal data?
- **rebalancing**: Is the drift analysis clear enough to decide whether to rebalance?
- **compliance**: Is pass/fail clear with specific violations listed?
- **goal_planning**: Is the gap analysis clear enough to discuss with the client?
- **transactions**: Are summary totals provided for quick review?

### F. Error Handling (1–5)

When the query is ambiguous or the client isn't found, does the agent handle it gracefully?

| Score | Criteria |
|-------|----------|
| 5 | Graceful handling with helpful suggestions (e.g., "Did you mean...?") |
| 4 | Handles error cleanly with a clear message |
| 3 | Handles error but message is generic (e.g., "No client found") |
| 2 | Poor error handling, confusing message |
| 1 | Crashes, shows stack trace, gives misleading info, or silently returns wrong data |

> **Note:** For test cases where no error is expected (most cases), score Error Handling as 5 if the response doesn't exhibit any error-like behavior. Only score lower if the response shows signs of poor error handling (e.g., "N/A" where data should exist, partial results without explanation).

---

## 2. Golden Answers — All 32 Test Cases

### Seed Data Reference

**Households:**

| Household | AUM | Risk Profile | Advisor |
|-----------|-----|-------------|---------|
| Johnson Family | $2,800,000 ($2.8M) | Moderate | Alex Morgan |
| Chen Family | $4,100,000 ($4.1M) | Aggressive | Alex Morgan |
| Martinez Family | $1,200,000 ($1.2M) | Conservative | Alex Morgan |
| Patel Family | $6,500,000 ($6.5M) | Moderate | Alex Morgan |
| Williams Family | $890,000 ($890K) | Growth | Alex Morgan |

**Target Allocations by Risk Profile:**

| Risk Profile | Equity | Fixed | Cash |
|-------------|--------|-------|------|
| Conservative | 30% | 60% | 10% |
| Moderate | 55% | 35% | 10% |
| Growth | 70% | 20% | 10% |
| Aggressive | 80% | 15% | 5% |

**Suitability Limits (Compliance):**
- Conservative: Equity max 50%
- Moderate: Equity max 70%
- Concentration risk: any single component > 80%
- Drift threshold (compliance): > 15% from target
- Drift threshold (rebalancing): > 5% from target

---

### Test 1: "Tell me about the Johnson household"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Johnson Family
Total AUM: $2.8M
Risk Profile: Moderate
Advisor: Alex Morgan

Members:
  - Sarah Johnson (Primary) | sarah.johnson@email.com
  - Tom Johnson (Spouse) | tom.johnson@email.com

Accounts:
  - Johnson IRA (IRA): $450K
  - Johnson 401k (401k): $820K
  - Johnson Family Trust (Trust): $1.53M
```

**Scoring Notes:**
- **Data Accuracy:** Must show $2.8M AUM, Moderate risk, Alex Morgan advisor. Account balances: $450K, $820K, $1.53M (total = $2.8M). Both members with correct roles.
- **Completeness:** Household name, AUM, risk, advisor, 2 members with roles/emails, 3 accounts with types/balances.
- **Relevance:** Direct answer to "tell me about" = client 360 view.
- **Actionability:** Provides complete client overview for any follow-up action.

---

### Test 2: "Tell me about the Chen family"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Chen Family
Total AUM: $4.1M
Risk Profile: Aggressive
Advisor: Alex Morgan

Members:
  - Wei Chen (Primary) | wei.chen@email.com
  - Lin Chen (Spouse) | lin.chen@email.com

Accounts:
  - Chen Brokerage (Brokerage): $2.2M
  - Chen Roth IRA (Roth IRA): $850K
  - Chen 529 Plan (529 Plan): $1.05M
```

**Scoring Notes:**
- **Data Accuracy:** AUM = $4.1M, Aggressive risk. 3 accounts: $2.2M + $850K + $1.05M = $4.1M. Wei = Primary, Lin = Spouse.
- **Completeness:** All 3 accounts must appear. Chen 529 Plan belongs to Lin Chen but is a household account.

---

### Test 3: "Tell me about the Martinez household"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Martinez Family
Total AUM: $1.2M
Risk Profile: Conservative
Advisor: Alex Morgan

Members:
  - Carlos Martinez (Primary) | carlos.martinez@email.com
  - Maria Martinez (Spouse) | maria.martinez@email.com

Accounts:
  - Martinez IRA (IRA): $680K
  - Martinez 401k (401k): $520K
```

**Scoring Notes:**
- **Data Accuracy:** AUM = $1.2M, Conservative risk. 2 accounts: $680K + $520K = $1.2M.
- **Completeness:** 2 members, 2 accounts.

---

### Test 4: "Tell me about the Patel family"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Patel Family
Total AUM: $6.5M
Risk Profile: Moderate
Advisor: Alex Morgan

Members:
  - Raj Patel (Primary) | raj.patel@email.com
  - Priya Patel (Spouse) | priya.patel@email.com

Accounts:
  - Patel Brokerage (Brokerage): $3.2M
  - Patel Trust (Trust): $2.1M
  - Patel Roth IRA (Roth IRA): $1.2M
```

**Scoring Notes:**
- **Data Accuracy:** AUM = $6.5M, Moderate risk. 3 accounts: $3.2M + $2.1M + $1.2M = $6.5M.
- **Completeness:** 2 members, 3 accounts.

---

### Test 5: "Tell me about the Williams family"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Williams Family
Total AUM: $890K
Risk Profile: Growth
Advisor: Alex Morgan

Members:
  - James Williams (Primary) | james.williams@email.com
  - Olivia Williams (Spouse) | olivia.williams@email.com

Accounts:
  - Williams 401k (401k): $520K
  - Williams IRA (IRA): $370K
```

**Scoring Notes:**
- **Data Accuracy:** AUM = $890K, Growth risk. 2 accounts: $520K + $370K = $890K.
- **Completeness:** 2 members, 2 accounts.

---

### Test 6: "How is Wei Chen's portfolio?"

**Expected:** Topic = `portfolio_review`, Action = `get_portfolio_summary`

**Golden Answer:**
```
Portfolio Review: Wei Chen
Household: Chen Family
Risk Profile: Aggressive

Accounts:
  - Chen Brokerage (Brokerage)
    Balance: $2.2M
    Allocation: 80% Equity / 15% Fixed / 5% Cash
    YTD Return: 12.3%

  - Chen Roth IRA (Roth IRA)
    Balance: $850K
    Allocation: 75% Equity / 20% Fixed / 5% Cash
    YTD Return: 11.1%

Total Portfolio Value: $3.05M
```

**Scoring Notes:**
- **Data Accuracy:** Wei Chen has 2 accounts (Brokerage + Roth IRA). The Chen 529 Plan belongs to Lin Chen, NOT Wei Chen. Total for Wei = $2,200,000 + $850,000 = $3,050,000 ($3.05M). YTD returns: 12.3% and 11.1%.
- **Completeness:** Must show both accounts with balance, allocation breakdown, and YTD return. Must NOT include Chen 529 Plan (that's Lin's).
- **Relevance:** Portfolio review = accounts, allocations, returns.
- **Actionability:** Clear performance data for advisor discussion.

---

### Test 7: "How is Raj Patel's portfolio performing?"

**Expected:** Topic = `portfolio_review`, Action = `get_portfolio_summary`

**Golden Answer:**
```
Portfolio Review: Raj Patel
Household: Patel Family
Risk Profile: Moderate

Accounts:
  - Patel Brokerage (Brokerage)
    Balance: $3.2M
    Allocation: 65% Equity / 25% Fixed / 10% Cash
    YTD Return: 9.7%

  - Patel Trust (Trust)
    Balance: $2.1M
    Allocation: 55% Equity / 35% Fixed / 10% Cash
    YTD Return: 6.9%

Total Portfolio Value: $5.3M
```

**Scoring Notes:**
- **Data Accuracy:** Raj Patel has 2 accounts (Brokerage + Trust). Patel Roth IRA belongs to Priya Patel, NOT Raj. Total for Raj = $3,200,000 + $2,100,000 = $5,300,000 ($5.3M).
- **Completeness:** 2 accounts with all fields. Must NOT include Patel Roth IRA (Priya's).

---

### Test 8: "Show me James Williams portfolio"

**Expected:** Topic = `portfolio_review`, Action = `get_portfolio_summary`

**Golden Answer:**
```
Portfolio Review: James Williams
Household: Williams Family
Risk Profile: Growth

Accounts:
  - Williams 401k (401k)
    Balance: $520K
    Allocation: 70% Equity / 20% Fixed / 10% Cash
    YTD Return: 10.2%

Total Portfolio Value: $520K
```

**Scoring Notes:**
- **Data Accuracy:** James Williams has 1 account (Williams 401k). Williams IRA belongs to Olivia Williams, NOT James. Total for James = $520,000 ($520K).
- **Completeness:** 1 account with all fields. Must NOT include Williams IRA (Olivia's).

---

### Test 9: "What are the Johnsons' retirement goals?"

**Expected:** Topic = `goal_planning`, Action = `get_financial_goals`

**Golden Answer:**
```
Financial Goals: Johnson Family

  Retirement
    Target: $3.0M
    Current: $2.8M
    Progress: 93.3%
    Gap: $200K
    Target Date: 2035-01-01

  College Fund - Emma
    Target: $200K
    Current: $145K
    Progress: 72.5%
    Gap: $55K
    Target Date: 2030-09-01
```

**Scoring Notes:**
- **Data Accuracy:** Retirement: target $3M, current $2.8M, progress = 2800000/3000000 = 93.3%, gap = $200K. College Fund: target $200K, current $145K, progress = 145000/200000 = 72.5%, gap = $55K.
- **Completeness:** Both goals must appear with all 5 fields (target, current, progress %, gap, date).
- **Relevance:** Query mentions "retirement goals" but should return ALL goals for the household (both Retirement and College Fund belong to Sarah Johnson in the Johnson household).

---

### Test 10: "What are the Patels' goals?"

**Expected:** Topic = `goal_planning`, Action = `get_financial_goals`

**Golden Answer:**
```
Financial Goals: Patel Family

  Retirement
    Target: $8.0M
    Current: $6.5M
    Progress: 81.3%
    Gap: $1.5M
    Target Date: 2033-01-01

  Philanthropy Fund
    Target: $1.0M
    Current: $650K
    Progress: 65.0%
    Gap: $350K
    Target Date: 2030-12-31
```

**Scoring Notes:**
- **Data Accuracy:** Retirement: target $8M, current $6.5M, progress = 6500000/8000000 = 81.25% ≈ 81.3%, gap = $1.5M. Philanthropy: target $1M, current $650K, progress = 650000/1000000 = 65.0%, gap = $350K.
- **Completeness:** Both goals (Raj's) must appear.

---

### Test 11: "What goals does Carlos Martinez have?"

**Expected:** Topic = `goal_planning`, Action = `get_financial_goals`

**Golden Answer:**
```
Financial Goals: Carlos Martinez

  Retirement
    Target: $1.5M
    Current: $1.2M
    Progress: 80.0%
    Gap: $300K
    Target Date: 2038-01-01

  Vacation Home
    Target: $350K
    Current: $120K
    Progress: 34.3%
    Gap: $230K
    Target Date: 2029-06-01
```

**Scoring Notes:**
- **Data Accuracy:** Retirement: target $1.5M, current $1.2M, progress = 1200000/1500000 = 80.0%, gap = $300K. Vacation Home: target $350K, current $120K, progress = 120000/350000 = 34.3%, gap = $230K.
- **Completeness:** Both goals must appear.

---

### Test 12: "Prep me for my meeting with Sarah Johnson"

**Expected:** Topic = `meeting_prep`, Action = `get_meeting_prep`

**Golden Answer:**
```
=== MEETING PREP BRIEF (Data Cloud) ===
Client: Sarah Johnson
Household: Johnson Family
Total AUM: $2.8M
Risk Profile: Moderate

--- Upcoming Meeting ---
Subject: Annual Portfolio Review
Date: [~7 days from now]
Location: Office - Conference Room A
Notes: Discuss retirement timeline and college fund progress
Action Items: Review trust allocation; Update beneficiary designations

--- Portfolio Snapshot ---
  Johnson IRA (IRA): $450K | YTD: 7.2%
  Johnson Family Trust (Trust): $1.53M | YTD: 5.8%

--- Goals Status ---
  Retirement: 93% ($2.8M / $3.0M)
  College Fund - Emma: 73% ($145K / $200K)

--- Suggested Talking Points ---
  1. Review portfolio performance and rebalancing needs
  2. Discuss progress toward financial goals
  3. Address life changes or updated priorities
  4. Review and confirm risk tolerance
```

**Scoring Notes:**
- **Data Accuracy:** Sarah's accounts are Johnson IRA ($450K, 7.2%) and Johnson Family Trust ($1.53M, 5.8%). Johnson 401k belongs to Tom, not Sarah. Goals: Retirement 93%, College Fund 73%.
- **Completeness:** Must include client info, household, meeting details, portfolio snapshot (Sarah's accounts only), goals, and talking points.
- **Actionability:** Talking points should be present and relevant. Meeting notes and action items provide context.

---

### Test 13: "Prep me for my meeting with Carlos"

**Expected:** Topic = `meeting_prep`, Action = `get_meeting_prep`

**Golden Answer:**
```
=== MEETING PREP BRIEF (Data Cloud) ===
Client: Carlos Martinez
Household: Martinez Family
Total AUM: $1.2M
Risk Profile: Conservative

--- Upcoming Meeting ---
Subject: Retirement Planning Check-in
Date: [~3 days from now]
Location: Office - Conference Room B
Notes: Carlos wants to discuss moving retirement date earlier
Action Items: Run updated retirement projections; Review vacation home savings plan

--- Portfolio Snapshot ---
  Martinez IRA (IRA): $680K | YTD: 4.1%

--- Goals Status ---
  Retirement: 80% ($1.2M / $1.5M)
  Vacation Home: 34% ($120K / $350K)

--- Suggested Talking Points ---
  1. Review portfolio performance and rebalancing needs
  2. Discuss progress toward financial goals
  3. Address life changes or updated priorities
  4. Review and confirm risk tolerance
```

**Scoring Notes:**
- **Data Accuracy:** Carlos has 1 account: Martinez IRA ($680K, 4.1%). Martinez 401k belongs to Maria. Goals: Retirement 80%, Vacation Home 34%.
- **Completeness:** Meeting is "Retirement Planning Check-in" at Conference Room B.
- **Actionability:** Meeting notes mention Carlos wants to move retirement earlier — highly relevant context.

---

### Test 14: "Prepare my meeting with Raj Patel"

**Expected:** Topic = `meeting_prep`, Action = `get_meeting_prep`

**Golden Answer:**
```
=== MEETING PREP BRIEF (Data Cloud) ===
Client: Raj Patel
Household: Patel Family
Total AUM: $6.5M
Risk Profile: Moderate

--- Upcoming Meeting ---
Subject: Estate Planning Discussion
Date: [~21 days from now]
Location: Client Home
Notes: Discuss philanthropy fund structure and estate plan updates
Action Items: Coordinate with estate attorney; Review trust documents

--- Portfolio Snapshot ---
  Patel Brokerage (Brokerage): $3.2M | YTD: 9.7%
  Patel Trust (Trust): $2.1M | YTD: 6.9%

--- Goals Status ---
  Retirement: 81% ($6.5M / $8.0M)
  Philanthropy Fund: 65% ($650K / $1.0M)

--- Suggested Talking Points ---
  1. Review portfolio performance and rebalancing needs
  2. Discuss progress toward financial goals
  3. Address life changes or updated priorities
  4. Review and confirm risk tolerance
```

**Scoring Notes:**
- **Data Accuracy:** Raj has 2 accounts: Patel Brokerage ($3.2M, 9.7%) and Patel Trust ($2.1M, 6.9%). Patel Roth IRA belongs to Priya. Goals: Retirement 81%, Philanthropy 65%.
- **Completeness:** Meeting is "Estate Planning Discussion" at Client Home.

---

### Test 15: "Does Sarah Johnson need rebalancing?"

**Expected:** Topic = `rebalancing_alerts`, Action = `check_rebalancing`

**Golden Answer:**
```
Rebalancing Analysis: Sarah Johnson
Household: Johnson Family
Risk Profile: Moderate
Target Allocation: 55% Equity / 35% Fixed / 10% Cash

Account Analysis:

  Johnson IRA (IRA)
    Current: 60% Equity / 30% Fixed / 10% Cash
    Equity: 60% (target 55%, drift +5%) ✓
    Fixed: 30% (target 35%, drift -5%) ✓
    Cash: 10% (target 10%, drift +0%) ✓
    Status: 🟢 Within tolerance

  Johnson Family Trust (Trust)
    Current: 50% Equity / 40% Fixed / 10% Cash
    Equity: 50% (target 55%, drift -5%) ✓
    Fixed: 40% (target 35%, drift +5%) ✓
    Cash: 10% (target 10%, drift +0%) ✓
    Status: 🟢 Within tolerance

=== SUMMARY ===
Overall: 🟢 ALL ACCOUNTS WITHIN TOLERANCE
Drift Threshold: >5% from target
```

**Scoring Notes:**
- **Data Accuracy:** Moderate target = 55/35/10. Sarah has 2 accounts (IRA + Trust). Johnson 401k belongs to Tom.
  - Johnson IRA (60/30/10): Equity drift = +5% (at threshold, NOT exceeding), Fixed drift = -5% (at threshold). The code uses `Math.abs(drift) > 5` so exactly 5% does NOT trigger a flag.
  - Johnson Family Trust (50/40/10): Equity drift = -5%, Fixed drift = +5%. Same — at threshold, not exceeding.
- **Completeness:** Per-account analysis with drift calculations, overall summary.
- **Actionability:** Clear that no rebalancing is needed — all within tolerance.

> **Critical calculation note:** The rebalancing threshold is `> 5%` (strictly greater than), so drifts of exactly 5% are WITHIN tolerance. Both of Sarah's accounts are at exactly 5% drift on Equity and Fixed, so the overall result is 🟢 ALL WITHIN TOLERANCE.

---

### Test 16: "Check rebalancing for Wei Chen"

**Expected:** Topic = `rebalancing_alerts`, Action = `check_rebalancing`

**Golden Answer:**
```
Rebalancing Analysis: Wei Chen
Household: Chen Family
Risk Profile: Aggressive
Target Allocation: 80% Equity / 15% Fixed / 10% Cash

Account Analysis:

  Chen Brokerage (Brokerage)
    Current: 80% Equity / 15% Fixed / 5% Cash
    Equity: 80% (target 80%, drift +0%) ✓
    Fixed: 15% (target 15%, drift +0%) ✓
    Cash: 5% (target 5%, drift +0%) ✓
    Status: 🟢 Within tolerance

  Chen Roth IRA (Roth IRA)
    Current: 75% Equity / 20% Fixed / 5% Cash
    Equity: 75% (target 80%, drift -5%) ✓
    Fixed: 20% (target 15%, drift +5%) ✓
    Cash: 5% (target 5%, drift +0%) ✓
    Status: 🟢 Within tolerance

=== SUMMARY ===
Overall: 🟢 ALL ACCOUNTS WITHIN TOLERANCE
Drift Threshold: >5% from target
```

**Scoring Notes:**
- **Data Accuracy:** Aggressive target = 80/15/5. Wei has 2 accounts (Brokerage + Roth IRA). Chen 529 Plan belongs to Lin.
  - Chen Brokerage (80/15/5): Exactly on target. All drifts = 0%.
  - Chen Roth IRA (75/20/5): Equity drift = -5% (at threshold, not exceeding), Fixed drift = +5% (at threshold).
  - Note: Aggressive Cash target is 5%, not 10%.
- **Completeness:** Both accounts analyzed. No flags.
- **Actionability:** Clear — no rebalancing needed.

---

### Test 17: "Does the Martinez account need rebalancing?"

**Expected:** Topic = `rebalancing_alerts`, Action = `check_rebalancing`

**Golden Answer:**
```
Rebalancing Analysis: Carlos Martinez
Household: Martinez Family
Risk Profile: Conservative
Target Allocation: 30% Equity / 60% Fixed / 10% Cash

Account Analysis:

  Martinez IRA (IRA)
    Current: 40% Equity / 50% Fixed / 10% Cash
    Equity: 40% (target 30%, drift +10%) ⚠️ DRIFT
    Fixed: 50% (target 60%, drift -10%) ⚠️ DRIFT
    Cash: 10% (target 10%, drift +0%) ✓
    Status: 🔴 REBALANCING NEEDED

=== SUMMARY ===
Overall: 🔴 REBALANCING RECOMMENDED (2 drift flags)
Drift Threshold: >5% from target
```

**Scoring Notes:**
- **Data Accuracy:** Conservative target = 30/60/10. The query says "Martinez account" — the agent finds Carlos Martinez (first match). Carlos has 1 account: Martinez IRA (40/50/10).
  - Martinez IRA: Equity drift = +10% (>5%, flagged), Fixed drift = -10% (>5%, flagged), Cash = 0%.
  - Martinez 401k belongs to Maria (35/55/10): Equity drift = +5% (at threshold, not flagged), Fixed drift = -5% (at threshold, not flagged).
  - Since the query resolves to Carlos, only Carlos's account (Martinez IRA) is shown.
- **Completeness:** Per-account drift analysis with flags.
- **Actionability:** Clear recommendation to rebalance with specific drift amounts.

> **Note:** If the agent resolves "Martinez account" to the household and shows both accounts, Maria's Martinez 401k (35/55/10) would show: Equity +5% ✓, Fixed -5% ✓, Cash 0% ✓ — within tolerance. Only Carlos's IRA would be flagged.

---

### Test 18: "Show me recent transactions for Sarah Johnson"

**Expected:** Topic = `transaction_history`, Action = `get_transactions`

**Golden Answer:**
```
Transaction History: Sarah Johnson
Showing last 7 transactions:

  [today-5] | Buy | $25K | VTI
    Vanguard Total Stock Market ETF

  [today-8] | Buy | $50K | AAPL
    Apple Inc

  [today-12] | Sell | $15K | BND
    Vanguard Total Bond Market ETF

  [today-15] | Dividend | $1.25K | VTI
    Quarterly dividend

  [today-20] | Sell | $30K | MSFT
    Microsoft Corp

  [today-25] | Dividend | $3.5K | JNJ
    Johnson & Johnson dividend

  [today-30] | Fee | $125
    Advisory fee Q1

=== SUMMARY ===
Total Buys: $75K
Total Sells: $45K
Total Dividends: $4.75K
Total Fees: $125
Net Activity: -$25.38K
```

**Scoring Notes:**
- **Data Accuracy:** Sarah has 7 transactions (TXN-001 through TXN-007) across Johnson IRA and Johnson Family Trust. Ordered by date descending.
  - Buys: VTI $25,000 + AAPL $50,000 = $75,000
  - Sells: BND $15,000 + MSFT $30,000 = $45,000
  - Dividends: VTI $1,250 + JNJ $3,500 = $4,750
  - Fees: $125
  - Net Activity = Sells + Dividends - Buys - Fees = $45,000 + $4,750 - $75,000 - $125 = -$25,375 (-$25.38K or -$25,375)
- **Completeness:** All 7 transactions with date, type, amount, symbol, description. Summary totals.
- **Actionability:** Summary totals give quick overview of activity direction (net outflow).

> **Note:** The action queries by Client__c, so only Sarah's transactions appear (not Tom's). The limit is 10, but Sarah only has 7.

---

### Test 19: "What are Wei Chen's latest transactions?"

**Expected:** Topic = `transaction_history`, Action = `get_transactions`

**Golden Answer:**
```
Transaction History: Wei Chen
Showing last 9 transactions:

  [today-3] | Buy | $100K | NVDA
    NVIDIA Corp

  [today-6] | Buy | $35K | QQQ
    Nasdaq 100 ETF

  [today-7] | Buy | $75K | TSLA
    Tesla Inc

  [today-10] | Sell | $50K | META
    Meta Platforms

  [today-14] | Sell | $80K | AMZN
    Amazon.com

  [today-18] | Dividend | $5.5K | AAPL
    Apple quarterly dividend

  [today-22] | Sell | $20K | GOOGL
    Alphabet Inc

  [today-28] | Dividend | $2.1K | MSFT
    Microsoft dividend

  [today-30] | Fee | $550
    Advisory fee Q1

=== SUMMARY ===
Total Buys: $210K
Total Sells: $150K
Total Dividends: $7.6K
Total Fees: $550
Net Activity: -$53.0K
```

**Scoring Notes:**
- **Data Accuracy:** Wei Chen has 9 transactions (TXN-011 through TXN-019) across Chen Brokerage and Chen Roth IRA. Ordered by date descending.
  - Buys: NVDA $100K + TSLA $75K + QQQ $35K = $210,000
  - Sells: META $50K + AMZN $80K + GOOGL $20K = $150,000
  - Dividends: AAPL $5,500 + MSFT $2,100 = $7,600
  - Fees: $550
  - Net = $150,000 + $7,600 - $210,000 - $550 = -$52,950 (-$53.0K)
- **Completeness:** All 9 transactions (under the 10 limit). Summary totals.

---

### Test 20: "Show me Raj Patel's transaction history"

**Expected:** Topic = `transaction_history`, Action = `get_transactions`

**Golden Answer:**
```
Transaction History: Raj Patel
Showing last 9 transactions:

  [today-2] | Buy | $200K | VTI
    Vanguard Total Stock Market

  [today-5] | Buy | $50K | BND
    Vanguard Total Bond Market

  [today-9] | Sell | $150K | AAPL
    Apple Inc - profit taking

  [today-13] | Buy | $100K | MSFT
    Microsoft Corp

  [today-17] | Dividend | $8K | VTI
    Quarterly dividend

  [today-19] | Dividend | $4.2K | VYM
    Vanguard High Dividend Yield

  [today-21] | Sell | $75K | GOOGL
    Alphabet - rebalancing

  [today-26] | Sell | $40K | JNJ
    Johnson & Johnson

  [today-30] | Fee | $800
    Advisory fee Q1

=== SUMMARY ===
Total Buys: $350K
Total Sells: $265K
Total Dividends: $12.2K
Total Fees: $800
Net Activity: -$73.6K
```

**Scoring Notes:**
- **Data Accuracy:** Raj Patel has 9 transactions (TXN-030 through TXN-038) across Patel Brokerage and Patel Trust. Ordered by date descending.
  - Buys: VTI $200K + BND $50K + MSFT $100K = $350,000
  - Sells: AAPL $150K + GOOGL $75K + JNJ $40K = $265,000
  - Dividends: VTI $8,000 + VYM $4,200 = $12,200
  - Fees: $800
  - Net = $265,000 + $12,200 - $350,000 - $800 = -$73,600 (-$73.6K)
- **Completeness:** All 9 transactions. Summary totals.

> **Note:** Priya Patel's transactions (TXN-039 through TXN-041) are NOT included — they belong to Priya, not Raj.

---

### Test 21: "Is the Patel account compliant?"

**Expected:** Topic = `compliance_check`, Action = `run_compliance`

**Golden Answer:**
```
=== COMPLIANCE CHECK ===
Household: Patel Family
Risk Profile: Moderate
Target: 55% Equity / 35% Fixed / 10% Cash

Account Checks:

  Patel Brokerage (Brokerage)
    Allocation: 65% Equity / 25% Fixed / 10% Cash
    ✓ Compliant
    (Suitability: Equity 65% < 70% moderate max → OK)
    (Concentration: No component > 80% → OK)
    (Drift: Equity +10%, Fixed -10%, Cash 0% — all ≤ 15% → OK)

  Patel Trust (Trust)
    Allocation: 55% Equity / 35% Fixed / 10% Cash
    ✓ Compliant
    (Exactly on target)

  Patel Roth IRA (Roth IRA)
    Allocation: 60% Equity / 30% Fixed / 10% Cash
    ✓ Compliant
    (Suitability: Equity 60% < 70% moderate max → OK)
    (Concentration: No component > 80% → OK)
    (Drift: Equity +5%, Fixed -5%, Cash 0% — all ≤ 15% → OK)

=== RESULT ===
Status: ✅ PASS — All accounts compliant
```

**Scoring Notes:**
- **Data Accuracy:** Patel = Moderate risk → target 55/35/10. Compliance checks all household accounts (Raj's + Priya's).
  - Patel Brokerage (65/25/10): Suitability — Equity 65% < 70% moderate max → PASS. Concentration — no component > 80% → PASS. Drift — Equity |65-55| = 10% ≤ 15% → PASS, Fixed |25-35| = 10% ≤ 15% → PASS.
  - Patel Trust (55/35/10): Exactly on target → PASS on all checks.
  - Patel Roth IRA (60/30/10): Suitability — Equity 60% < 70% → PASS. Concentration → PASS. Drift — Equity |60-55| = 5% ≤ 15% → PASS, Fixed |30-35| = 5% ≤ 15% → PASS.
- **Completeness:** All 3 accounts checked, overall PASS result.
- **Actionability:** Clear PASS with no violations — advisor can confirm compliance to client.

> **Critical note:** The compliance drift threshold is `> 15%` (not the rebalancing 5% threshold). All Patel accounts have drifts ≤ 10%, well within the 15% compliance threshold. Overall result: **PASS**.

---

### Test 22: "Run a compliance check on the Martinez household"

**Expected:** Topic = `compliance_check`, Action = `run_compliance`

**Golden Answer:**
```
=== COMPLIANCE CHECK ===
Household: Martinez Family
Risk Profile: Conservative
Target: 30% Equity / 60% Fixed / 10% Cash

Account Checks:

  Martinez IRA (IRA)
    Allocation: 40% Equity / 50% Fixed / 10% Cash
    ✓ Compliant
    (Suitability: Equity 40% < 50% conservative max → OK)
    (Concentration: No component > 80% → OK)
    (Drift: Equity |40-30| = 10% ≤ 15% → OK, Fixed |50-60| = 10% ≤ 15% → OK)

  Martinez 401k (401k)
    Allocation: 35% Equity / 55% Fixed / 10% Cash
    ✓ Compliant
    (Suitability: Equity 35% < 50% conservative max → OK)
    (Concentration: No component > 80% → OK)
    (Drift: Equity |35-30| = 5% ≤ 15% → OK, Fixed |55-60| = 5% ≤ 15% → OK)

=== RESULT ===
Status: ✅ PASS — All accounts compliant
```

**Scoring Notes:**
- **Data Accuracy:** Martinez = Conservative → target 30/60/10. Conservative suitability limit: Equity max 50%.
  - Martinez IRA (40/50/10): Suitability — Equity 40% < 50% → PASS. Drift — Equity 10%, Fixed 10% — both ≤ 15% → PASS.
  - Martinez 401k (35/55/10): Suitability — Equity 35% < 50% → PASS. Drift — Equity 5%, Fixed 5% — both ≤ 15% → PASS.
- **Completeness:** Both accounts checked, overall PASS.
- **Actionability:** Clear PASS result.

---

### Test 23: "Check compliance for Wei Chen"

**Expected:** Topic = `compliance_check`, Action = `run_compliance`

**Golden Answer:**
```
=== COMPLIANCE CHECK ===
Household: Chen Family
Risk Profile: Aggressive
Target: 80% Equity / 15% Fixed / 5% Cash

Account Checks:

  Chen Brokerage (Brokerage)
    Allocation: 80% Equity / 15% Fixed / 5% Cash
    ✓ Compliant
    (Exactly on target)
    (Concentration: Equity at 80% — at threshold, not exceeding → OK)

  Chen Roth IRA (Roth IRA)
    Allocation: 75% Equity / 20% Fixed / 5% Cash
    ✓ Compliant
    (Drift: Equity |75-80| = 5% ≤ 15% → OK, Fixed |20-15| = 5% ≤ 15% → OK)

  Chen 529 Plan (529 Plan)
    Allocation: 65% Equity / 30% Fixed / 5% Cash
    ✓ Compliant
    (Drift: Equity |65-80| = 15% ≤ 15% → OK, Fixed |30-15| = 15% ≤ 15% → OK)

=== RESULT ===
Status: ✅ PASS — All accounts compliant
```

**Scoring Notes:**
- **Data Accuracy:** Chen = Aggressive → target 80/15/5. Compliance checks all household accounts.
  - Chen Brokerage (80/15/5): Exactly on target. Concentration: Equity at 80% — the threshold is `> 80%`, so exactly 80% does NOT trigger. PASS.
  - Chen Roth IRA (75/20/5): Drift — Equity 5%, Fixed 5% — both ≤ 15% → PASS. No suitability rule for Aggressive profile in the code.
  - Chen 529 Plan (65/30/5): Drift — Equity |65-80| = 15%, Fixed |30-15| = 15% — both at threshold (≤ 15%, since check is `> 15%`). PASS.
- **Completeness:** All 3 household accounts checked.
- **Actionability:** Clear PASS. Note that Chen 529 Plan is at the edge of compliance drift threshold.

> **Critical calculation:** The compliance code checks `drift > 15`, so exactly 15% is NOT a violation. Chen 529 Plan's Equity and Fixed drifts are exactly 15% — they PASS.

---

### Test 24: "Who referred the Williams family?"

**Expected:** Topic = `referral_tracking`, Action = `get_referrals`

**Golden Answer:**
```
Referral Tracking: Williams Family

  Williams Referral
    Source: LinkedIn Campaign Q4
    Type: Marketing
    Date: 2024-10-05
    Status: New
    Estimated Value: $1.2M

=== SUMMARY ===
Total Referrals: 1
Total Estimated Value: $1.2M
```

**Scoring Notes:**
- **Data Accuracy:** Williams referral: Source = "LinkedIn Campaign Q4", Type = "Marketing", Date = 2024-10-05, Status = "New", Value = $1,200,000 ($1.2M).
- **Completeness:** All referral fields present plus summary.
- **Relevance:** Directly answers "who referred" with source information.
- **Actionability:** Status is "New" — advisor knows this is a fresh lead.

---

### Test 25: "Who referred the Johnsons?"

**Expected:** Topic = `referral_tracking`, Action = `get_referrals`

**Golden Answer:**
```
Referral Tracking: Johnson Family

  Johnson Referral
    Source: Dr. Robert Kim
    Type: Client
    Date: 2023-03-15
    Status: Converted
    Estimated Value: $2.8M

=== SUMMARY ===
Total Referrals: 1
Total Estimated Value: $2.8M
```

**Scoring Notes:**
- **Data Accuracy:** Johnson referral: Source = "Dr. Robert Kim", Type = "Client", Date = 2023-03-15, Status = "Converted", Value = $2,800,000 ($2.8M).
- **Completeness:** All fields present.
- **Actionability:** Status is "Converted" — this is a completed referral.

---

### Test 26: "What's the referral source for the Patels?"

**Expected:** Topic = `referral_tracking`, Action = `get_referrals`

**Golden Answer:**
```
Referral Tracking: Patel Family

  Patel Referral
    Source: Sarah Johnson
    Type: Client
    Date: 2021-06-10
    Status: Converted
    Estimated Value: $6.5M

=== SUMMARY ===
Total Referrals: 1
Total Estimated Value: $6.5M
```

**Scoring Notes:**
- **Data Accuracy:** Patel referral: Source = "Sarah Johnson", Type = "Client", Date = 2021-06-10, Status = "Converted", Value = $6,500,000 ($6.5M).
- **Completeness:** All fields present.
- **Relevance:** Directly answers "referral source" — Sarah Johnson referred the Patels.
- **Actionability:** Interesting cross-reference: Sarah Johnson (another client) referred the Patels.

---

### Test 27: "Transfer me to a specialist"

**Expected:** Topic = `escalation`

**Golden Answer:**
```
I'll transfer you to a specialist right away. Please hold while I connect you with a human representative who can assist you further.
```

**Scoring Notes:**
- **Data Accuracy:** N/A — no data to verify.
- **Completeness:** Should acknowledge the request and indicate transfer is happening.
- **Relevance:** Must escalate, not try to answer a question.
- **Tone:** Professional, reassuring.
- **Actionability:** Clear that a transfer is in progress.
- **Error Handling:** Should not error — this is a supported action.

---

### Test 28: "I need to speak to a human"

**Expected:** Topic = `escalation`

**Golden Answer:**
```
I understand you'd like to speak with a human representative. I'm transferring you now. A specialist will be with you shortly.
```

**Scoring Notes:**
- **Data Accuracy:** N/A.
- **Completeness:** Acknowledgment + transfer indication.
- **Relevance:** Must escalate.
- **Tone:** Empathetic, professional.

---

### Test 29: "What is the weather today?"

**Expected:** Topic = `off_topic`

**Golden Answer:**
```
I'm focused on wealth advisory services and can't help with weather information. I can assist you with:
- Client lookups
- Portfolio reviews
- Goal planning
- Meeting preparation
- Rebalancing analysis
- Transaction history
- Compliance checks
- Referral tracking

How can I help you with your wealth advisory needs?
```

**Scoring Notes:**
- **Data Accuracy:** N/A.
- **Completeness:** Should list available capabilities.
- **Relevance:** Must redirect to wealth advisory topics, not attempt to answer.
- **Tone:** Polite but firm redirect.
- **Error Handling:** Graceful handling of off-topic request.

---

### Test 30: "What's the stock price of Apple?"

**Expected:** Topic = `off_topic`

**Golden Answer:**
```
I'm not able to provide real-time stock prices. I'm designed to help with wealth advisory tasks such as:
- Client lookups
- Portfolio reviews
- Goal planning
- Meeting preparation
- Rebalancing analysis
- Transaction history
- Compliance checks
- Referral tracking

Would you like help with any of these?
```

**Scoring Notes:**
- **Data Accuracy:** N/A.
- **Completeness:** Should list capabilities.
- **Relevance:** Must redirect. Should NOT attempt to provide a stock price.
- **Tone:** Helpful redirect without being dismissive.

---

### Test 31: "Tell me about the Johnsons"

**Expected:** Topic = `client_lookup`, Action = `get_client_360`

**Golden Answer:**
```
Household: Johnson Family
Total AUM: $2.8M
Risk Profile: Moderate
Advisor: Alex Morgan

Members:
  - Sarah Johnson (Primary) | sarah.johnson@email.com
  - Tom Johnson (Spouse) | tom.johnson@email.com

Accounts:
  - Johnson IRA (IRA): $450K
  - Johnson 401k (401k): $820K
  - Johnson Family Trust (Trust): $1.53M
```

**Scoring Notes:**
- **Data Accuracy:** Same as Test 1. The plural "Johnsons" should resolve to "Johnson Family" via fuzzy matching.
- **Completeness:** Same as Test 1.
- **Relevance:** Tests fuzzy matching — "Johnsons" (plural) → "Johnson Family".
- **Error Handling:** Should NOT fail due to the plural form. The `cleanClientName()` regex strips the trailing 's.

---

### Test 32: "How is Carlos doing on his goals?"

**Expected:** Topic = `goal_planning`, Action = `get_financial_goals`

**Golden Answer:**
```
Financial Goals: Carlos Martinez

  Retirement
    Target: $1.5M
    Current: $1.2M
    Progress: 80.0%
    Gap: $300K
    Target Date: 2038-01-01

  Vacation Home
    Target: $350K
    Current: $120K
    Progress: 34.3%
    Gap: $230K
    Target Date: 2029-06-01
```

**Scoring Notes:**
- **Data Accuracy:** Same as Test 11. First-name-only "Carlos" should resolve to "Carlos Martinez" via fuzzy matching.
- **Completeness:** Same as Test 11.
- **Relevance:** Tests first-name-only matching — "Carlos" → "Carlos Martinez".
- **Error Handling:** Should NOT fail due to first-name-only input. The name-part fallback in the Apex action handles this.

---

## 3. LLM Judge Prompt Template

Use this prompt template with any LLM (GPT-4, Claude, Gemini, etc.) to evaluate agent responses:

```
You are evaluating the response of a wealth advisor AI agent. Your job is to score the response on 6 dimensions.

=== CONTEXT ===
QUERY: {query}
EXPECTED TOPIC: {topic}
EXPECTED ACTION: {action}
GOLDEN ANSWER: {golden_answer}
ACTUAL RESPONSE: {actual_response}

=== SCORING RUBRIC ===

Score each dimension from 1 (worst) to 5 (best):

1. DATA ACCURACY (1-5)
   Are all data points (names, dollar amounts, percentages, dates) correct?
   Compare every number in the actual response against the golden answer.
   - 5 = All data points match exactly
   - 4 = All key data correct, minor formatting differences
   - 3 = Most data correct, 1-2 minor discrepancies
   - 2 = Several errors or one major error
   - 1 = Major data errors or fabricated data

2. COMPLETENESS (1-5)
   Does the response include all expected information from the golden answer?
   - 5 = All expected fields present
   - 4 = All key fields, 1 minor field missing
   - 3 = Key fields present, some secondary missing
   - 2 = Several important fields missing
   - 1 = Most fields missing

3. RELEVANCE (1-5)
   Does the response directly answer the question asked?
   - 5 = Directly answers with no tangents
   - 4 = Answers with minor useful additions
   - 3 = Answers but includes irrelevant info
   - 2 = Partially addresses the question
   - 1 = Off-topic or wrong question answered

4
. TONE and PROFESSIONALISM (1-5)
   Is the response appropriate for a wealth advisor context?
   - 5 = Professional, clear, well-structured
   - 4 = Professional with minor issues
   - 3 = Acceptable but could be more polished
   - 2 = Somewhat unprofessional or confusing
   - 1 = Unprofessional or inappropriate

5. ACTIONABILITY (1-5)
   Does the response provide actionable insights for the advisor?
   - 5 = Clear next steps or decision-ready data
   - 4 = Good actionable info with minor gaps
   - 3 = Some actionable info but vague
   - 2 = Limited actionable content
   - 1 = No actionable information

6. ERROR HANDLING (1-5)
   If the query is ambiguous or edge-case, does the agent handle it gracefully?
   - 5 = Graceful handling with helpful suggestions
   - 4 = Clean error message
   - 3 = Generic error handling
   - 2 = Poor error handling
   - 1 = Crashes, stack traces, or misleading info
   (If no error scenario applies, score 5 if no error-like behavior is present)

=== OUTPUT FORMAT ===

Provide your evaluation in this exact JSON format:

{
  "data_accuracy": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "completeness": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "relevance": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "tone": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "actionability": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "error_handling": {
    "score": <1-5>,
    "justification": "<brief explanation>"
  },
  "overall_score": <average of all 6 scores, rounded to 1 decimal>,
  "pass": <true if overall_score >= 3.5 AND no dimension < 2 AND data_accuracy >= 3>,
  "key_issues": ["<issue 1>", "<issue 2>", ...]
}
```

### Simplified Prompt (for quick evaluations)

```
Rate this wealth advisor agent response (1-5 each):

Query: {query}
Expected: {golden_answer_summary}
Actual: {actual_response}

Scores: Data Accuracy | Completeness | Relevance | Tone | Actionability | Error Handling
Pass if average >= 3.5, no score < 2, data accuracy >= 3.
```

---

## 4. Scoring Thresholds

### Pass/Fail Rules

| Rule | Threshold | Rationale |
|------|-----------|-----------|
| Overall Pass | Average of 6 dimensions >= 3.5 | Minimum acceptable quality |
| Critical Fail — Data Accuracy | Data Accuracy < 3 | Wrong data is worse than incomplete data in financial services |
| Critical Fail — Any Dimension | Any single dimension < 2 | No dimension should be severely deficient |
| Warning | Any dimension = 2 | Needs improvement but not a hard fail |

### Quality Tiers

| Tier | Overall Score | Interpretation |
|------|--------------|----------------|
| Excellent | 4.5 – 5.0 | Production-ready, exceeds expectations |
| Good | 3.5 – 4.4 | Acceptable for production, minor improvements possible |
| Needs Work | 2.5 – 3.4 | Below threshold, requires fixes before production |
| Poor | 1.0 – 2.4 | Significant issues, major rework needed |

### Per-Topic Minimum Expectations

| Topic | Min Data Accuracy | Min Completeness | Min Actionability |
|-------|-------------------|------------------|-------------------|
| client_lookup | 4 | 4 | 3 |
| portfolio_review | 4 | 4 | 4 |
| goal_planning | 4 | 4 | 4 |
| meeting_prep | 4 | 4 | 5 |
| rebalancing_alerts | 5 | 4 | 5 |
| transaction_history | 4 | 4 | 4 |
| compliance_check | 5 | 5 | 5 |
| referral_tracking | 4 | 4 | 3 |
| escalation | N/A | 3 | 4 |
| off_topic | N/A | 3 | 3 |

> **Compliance and rebalancing require the highest accuracy** — incorrect compliance results or drift calculations could lead to regulatory violations.

---

## 5. Batch Evaluation Script

### Conceptual Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Run Agent   │────▶│  Collect     │────▶│  LLM Judge   │────▶│  Aggregate   │
│  Test Suite  │     │  Responses   │     │  Evaluation  │     │  Report      │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Python-like Pseudocode

```python
import json
import subprocess
from dataclasses import dataclass

@dataclass
class TestCase:
    number: int
    query: str
    expected_topic: str
    expected_action: str
    golden_answer: str

@dataclass
class EvalResult:
    test_number: int
    query: str
    topic_match: bool
    action_match: bool
    data_accuracy: int
    completeness: int
    relevance: int
    tone: int
    actionability: int
    error_handling: int
    overall_score: float
    passed: bool
    key_issues: list

# ── Step 1: Define test cases with golden answers ──
TEST_CASES = [
    TestCase(1, "Tell me about the Johnson household", "client_lookup", "get_client_360",
             "Household: Johnson Family\nTotal AUM: $2.8M\nRisk Profile: Moderate\n..."),
    TestCase(2, "Tell me about the Chen family", "client_lookup", "get_client_360",
             "Household: Chen Family\nTotal AUM: $4.1M\nRisk Profile: Aggressive\n..."),
    # ... all 32 test cases with full golden answers from Section 2
]

# ── Step 2: Run agent tests via Salesforce CLI ──
def run_agent_tests():
    """Execute all 32 test cases via sf agent test run"""
    result = subprocess.run(
        ["sf", "agent", "test", "run",
         "--api-name", "WA_P1to5_Advisor_Full_Test",
         "--wait", "30",
         "--result-format", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

# ── Step 3: Extract actual responses ──
def extract_responses(test_results):
    """Parse test results to get actual agent responses"""
    responses = {}
    for case in test_results.get("testCases", []):
        test_num = case["number"]
        actual_response = case.get("actualResponse", "")
        topic_match = case.get("topicMatch", False)
        action_match = case.get("actionMatch", False)
        responses[test_num] = {
            "response": actual_response,
            "topic_match": topic_match,
            "action_match": action_match
        }
    return responses

# ── Step 4: Evaluate each response with LLM judge ──
def evaluate_with_llm(query, golden_answer, actual_response, llm_client):
    """Send (query, golden, actual) to LLM judge and parse scores"""
    prompt = LLM_JUDGE_PROMPT_TEMPLATE.format(
        query=query,
        topic=test_case.expected_topic,
        action=test_case.expected_action,
        golden_answer=golden_answer,
        actual_response=actual_response
    )

    response = llm_client.chat(
        model="gpt-4",  # or "claude-3-opus", etc.
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0  # deterministic scoring
    )

    return json.loads(response.content)

# ── Step 5: Run full evaluation pipeline ──
def run_evaluation():
    print("Step 1: Running agent test suite...")
    test_results = run_agent_tests()

    print("Step 2: Extracting responses...")
    responses = extract_responses(test_results)

    print("Step 3: Evaluating with LLM judge...")
    results = []
    for tc in TEST_CASES:
        resp = responses.get(tc.number, {})
        actual = resp.get("response", "NO RESPONSE")

        eval_scores = evaluate_with_llm(
            tc.query, tc.golden_answer, actual, llm_client
        )

        result = EvalResult(
            test_number=tc.number,
            query=tc.query,
            topic_match=resp.get("topic_match", False),
            action_match=resp.get("action_match", False),
            data_accuracy=eval_scores["data_accuracy"]["score"],
            completeness=eval_scores["completeness"]["score"],
            relevance=eval_scores["relevance"]["score"],
            tone=eval_scores["tone"]["score"],
            actionability=eval_scores["actionability"]["score"],
            error_handling=eval_scores["error_handling"]["score"],
            overall_score=eval_scores["overall_score"],
            passed=eval_scores["pass"],
            key_issues=eval_scores.get("key_issues", [])
        )
        results.append(result)

    print("Step 4: Generating report...")
    generate_report(results)
    return results

# ── Step 6: Generate report ──
def generate_report(results):
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    avg_scores = {
        "data_accuracy": sum(r.data_accuracy for r in results) / total,
        "completeness": sum(r.completeness for r in results) / total,
        "relevance": sum(r.relevance for r in results) / total,
        "tone": sum(r.tone for r in results) / total,
        "actionability": sum(r.actionability for r in results) / total,
        "error_handling": sum(r.error_handling for r in results) / total,
    }
    overall_avg = sum(avg_scores.values()) / 6

    print(f"\n{'='*60}")
    print(f"  WA_P1to5_Advisor — LLM-as-Judge Evaluation Report")
    print(f"{'='*60}")
    print(f"  Total Tests:  {total}")
    print(f"  Passed:       {passed} ({passed/total*100:.0f}%)")
    print(f"  Failed:       {failed} ({failed/total*100:.0f}%)")
    print(f"  Overall Avg:  {overall_avg:.1f}/5.0")
    print(f"")
    print(f"  Dimension Averages:")
    for dim, avg in avg_scores.items():
        print(f"    {dim:20s}: {avg:.1f}/5.0")
    print(f"{'='*60}")

    # Print failures
    if failed > 0:
        print(f"\n  FAILED TESTS:")
        for r in results:
            if not r.passed:
                print(f"    Test {r.test_number}: {r.query}")
                print(f"      Overall: {r.overall_score:.1f} | Issues: {', '.join(r.key_issues)}")

# ── Entry point ──
if __name__ == "__main__":
    run_evaluation()
```

### Running the Evaluation

```bash
# 1. Ensure seed data is loaded
sf apex run --file scripts/apex/seed-data.apex --target-org your-org

# 2. Run the agent test suite (collects topic/action matches + responses)
sf agent test run --api-name WA_P1to5_Advisor_Full_Test --wait 30 --result-format json > test-results.json

# 3. Run the LLM judge evaluation (using the script above)
python scripts/evaluate-agent.py --results test-results.json --output eval-report.json

# 4. View the report
cat eval-report.json | python -m json.tool
```

---

## 6. Salesforce-Specific: bot_response_rating

### How bot_response_rating Works

Salesforce's `bot_response_rating` expectation in `AiEvaluationDefinition` uses Einstein's built-in LLM to judge whether the agent's actual response matches the `expectedValue` description. Under the hood:

1. The test runner sends the user utterance to the agent and captures the actual response.
2. Einstein's LLM receives the `expectedValue` string and the actual response.
3. The LLM evaluates whether the actual response satisfies the description in `expectedValue`.
4. It returns a rating (typically pass/fail or a confidence score).

### Current expectedValue Strings (from WA_P1to5_Advisor_Full_Test)

The current `expectedValue` strings are generic:

| Test | Current expectedValue |
|------|----------------------|
| 1 | "Returns Johnson household with AUM and members" |
| 6 | "Returns portfolio with allocation and returns for Wei Chen" |
| 15 | "Returns drift analysis for Sarah Johnson" |
| 18 | "Returns recent transactions for Sarah Johnson" |
| 21 | "Returns compliance report for the Patel account" |
| 24 | "Returns referral info for the Williams family" |

These are too vague for rigorous evaluation. The LLM judge can only verify that the response is "about" the right topic, not that the data is correct.

### Mapping Our 6 Dimensions to bot_response_rating

| Our Dimension | bot_response_rating Coverage | Gap |
|---------------|------------------------------|-----|
| Data Accuracy | Partial — only if expectedValue mentions specific numbers | Major gap: generic descriptions don't verify data |
| Completeness | Partial — only if expectedValue lists required fields | Gap: "Returns household with AUM and members" doesn't specify which members |
| Relevance | Good — the LLM naturally checks if the response matches the description | Covered |
| Tone | Minimal — not typically part of expectedValue | Gap: would need explicit tone instructions |
| Actionability | Minimal — not typically evaluated | Gap: would need explicit actionability criteria |
| Error Handling | Minimal — only for error-specific test cases | Gap: not evaluated for happy-path cases |

### Recommendations: Writing Better expectedValue Strings

To make `bot_response_rating` more rigorous, embed specific data points and structural requirements in the `expectedValue`:

#### Before (Generic)
```xml
<expectedValue>Returns Johnson household with AUM and members</expectedValue>
```

#### After (Specific)
```xml
<expectedValue>Response must include: Household name "Johnson Family", Total AUM of $2.8M, Risk Profile "Moderate", Advisor "Alex Morgan", two members (Sarah Johnson as Primary, Tom Johnson as Spouse), and three accounts (Johnson IRA at $450K, Johnson 401k at $820K, Johnson Family Trust at $1.53M). Data must be accurate and complete.</expectedValue>
```

### Improved expectedValue Strings for All 32 Tests

**Test 1:**
```
Response includes Johnson Family household with $2.8M AUM, Moderate risk, Alex Morgan advisor, members Sarah Johnson (Primary) and Tom Johnson (Spouse), and accounts Johnson IRA ($450K), Johnson 401k ($820K), Johnson Family Trust ($1.53M).
```

**Test 2:**
```
Response includes Chen Family household with $4.1M AUM, Aggressive risk, Alex Morgan advisor, members Wei Chen (Primary) and Lin Chen (Spouse), and accounts Chen Brokerage ($2.2M), Chen Roth IRA ($850K), Chen 529 Plan ($1.05M).
```

**Test 3:**
```
Response includes Martinez Family household with $1.2M AUM, Conservative risk, Alex Morgan advisor, members Carlos Martinez (Primary) and Maria Martinez (Spouse), and accounts Martinez IRA ($680K), Martinez 401k ($520K).
```

**Test 4:**
```
Response includes Patel Family household with $6.5M AUM, Moderate risk, Alex Morgan advisor, members Raj Patel (Primary) and Priya Patel (Spouse), and accounts Patel Brokerage ($3.2M), Patel Trust ($2.1M), Patel Roth IRA ($1.2M).
```

**Test 5:**
```
Response includes Williams Family household with $890K AUM, Growth risk, Alex Morgan advisor, members James Williams (Primary) and Olivia Williams (Spouse), and accounts Williams 401k ($520K), Williams IRA ($370K).
```

**Test 6:**
```
Response shows Wei Chen portfolio with Chen Family household, Aggressive risk. Must include Chen Brokerage ($2.2M, 80/15/5 allocation, 12.3% YTD) and Chen Roth IRA ($850K, 75/20/5 allocation, 11.1% YTD). Total portfolio $3.05M. Must NOT include Chen 529 Plan (that belongs to Lin Chen).
```

**Test 7:**
```
Response shows Raj Patel portfolio with Patel Family household, Moderate risk. Must include Patel Brokerage ($3.2M, 65/25/10 allocation, 9.7% YTD) and Patel Trust ($2.1M, 55/35/10 allocation, 6.9% YTD). Total portfolio $5.3M. Must NOT include Patel Roth IRA (belongs to Priya).
```

**Test 8:**
```
Response shows James Williams portfolio with Williams Family household, Growth risk. Must include Williams 401k ($520K, 70/20/10 allocation, 10.2% YTD). Total portfolio $520K. Must NOT include Williams IRA (belongs to Olivia).
```

**Test 9:**
```
Response shows Johnson Family financial goals: Retirement (target $3M, current $2.8M, 93.3% progress, $200K gap, target 2035-01-01) and College Fund - Emma (target $200K, current $145K, 72.5% progress, $55K gap, target 2030-09-01).
```

**Test 10:**
```
Response shows Patel Family financial goals: Retirement (target $8M, current $6.5M, 81.3% progress, $1.5M gap, target 2033-01-01) and Philanthropy Fund (target $1M, current $650K, 65.0% progress, $350K gap, target 2030-12-31).
```

**Test 11:**
```
Response shows Carlos Martinez financial goals: Retirement (target $1.5M, current $1.2M, 80.0% progress, $300K gap, target 2038-01-01) and Vacation Home (target $350K, current $120K, 34.3% progress, $230K gap, target 2029-06-01).
```

**Test 12:**
```
Response is a meeting prep brief for Sarah Johnson including: Johnson Family household, $2.8M AUM, Moderate risk, meeting "Annual Portfolio Review" at Conference Room A, notes about retirement timeline and college fund, portfolio snapshot with Johnson IRA ($450K, 7.2% YTD) and Johnson Family Trust ($1.53M, 5.8% YTD), goals status (Retirement 93%, College Fund 73%), and talking points.
```

**Test 13:**
```
Response is a meeting prep brief for Carlos Martinez including: Martinez Family household, $1.2M AUM, Conservative risk, meeting "Retirement Planning Check-in" at Conference Room B, notes about moving retirement date earlier, portfolio snapshot with Martinez IRA ($680K, 4.1% YTD), goals status (Retirement 80%, Vacation Home 34%), and talking points.
```

**Test 14:**
```
Response is a meeting prep brief for Raj Patel including: Patel Family household, $6.5M AUM, Moderate risk, meeting "Estate Planning Discussion" at Client Home, notes about philanthropy fund and estate plan, portfolio snapshot with Patel Brokerage ($3.2M, 9.7% YTD) and Patel Trust ($2.1M, 6.9% YTD), goals status (Retirement 81%, Philanthropy 65%), and talking points.
```

**Test 15:**
```
Response shows rebalancing analysis for Sarah Johnson with Moderate risk, target 55/35/10. Johnson IRA (60/30/10): Equity +5%, Fixed -5% — within tolerance. Johnson Family Trust (50/40/10): Equity -5%, Fixed +5% — within tolerance. Overall: all accounts within tolerance, no rebalancing needed.
```

**Test 16:**
```
Response shows rebalancing analysis for Wei Chen with Aggressive risk, target 80/15/5. Chen Brokerage (80/15/5): exactly on target. Chen Roth IRA (75/20/5): Equity -5%, Fixed +5% — within tolerance. Overall: all accounts within tolerance.
```

**Test 17:**
```
Response shows rebalancing analysis for Martinez with Conservative risk, target 30/60/10. Martinez IRA (40/50/10): Equity +10% drift (flagged), Fixed -10% drift (flagged). Overall: rebalancing recommended with 2 drift flags.
```

**Test 18:**
```
Response shows Sarah Johnson's 7 transactions including buys (VTI $25K, AAPL $50K), sells (BND $15K, MSFT $30K), dividends (VTI $1.25K, JNJ $3.5K), and fee ($125). Summary: Total Buys $75K, Total Sells $45K, Total Dividends $4.75K, Total Fees $125, Net Activity approximately -$25.4K.
```

**Test 19:**
```
Response shows Wei Chen's 9 transactions including buys (NVDA $100K, TSLA $75K, QQQ $35K), sells (META $50K, AMZN $80K, GOOGL $20K), dividends (AAPL $5.5K, MSFT $2.1K), and fee ($550). Summary: Total Buys $210K, Total Sells $150K, Total Dividends $7.6K, Total Fees $550, Net Activity approximately -$53K.
```

**Test 20:**
```
Response shows Raj Patel's 9 transactions including buys (VTI $200K, BND $50K, MSFT $100K), sells (AAPL $150K, GOOGL $75K, JNJ $40K), dividends (VTI $8K, VYM $4.2K), and fee ($800). Summary: Total Buys $350K, Total Sells $265K, Total Dividends $12.2K, Total Fees $800, Net Activity approximately -$73.6K.
```

**Test 21:**
```
Response shows compliance check for Patel Family with Moderate risk, target 55/35/10. All 3 accounts (Patel Brokerage 65/25/10, Patel Trust 55/35/10, Patel Roth IRA 60/30/10) pass all checks: suitability (all equity < 70% moderate max), no concentration risk, all drifts within 15% threshold. Overall: PASS.
```

**Test 22:**
```
Response shows compliance check for Martinez Family with Conservative risk, target 30/60/10. Both accounts (Martinez IRA 40/50/10, Martinez 401k 35/55/10) pass: suitability (all equity < 50% conservative max), no concentration risk, all drifts within 15% threshold. Overall: PASS.
```

**Test 23:**
```
Response shows compliance check for Chen Family with Aggressive risk, target 80/15/5. All 3 accounts (Chen Brokerage 80/15/5, Chen Roth IRA 75/20/5, Chen 529 Plan 65/30/5) pass: no concentration risk (equity at 80% is at threshold not exceeding), all drifts within 15% threshold. Overall: PASS.
```

**Test 24:**
```
Response shows Williams Family referral: source "LinkedIn Campaign Q4", type "Marketing", date 2024-10-05, status "New", estimated value $1.2M. Total referrals: 1, total value: $1.2M.
```

**Test 25:**
```
Response shows Johnson Family referral: source "Dr. Robert Kim", type "Client", date 2023-03-15, status "Converted", estimated value $2.8M. Total referrals: 1, total value: $2.8M.
```

**Test 26:**
```
Response shows Patel Family referral: source "Sarah Johnson", type "Client", date 2021-06-10, status "Converted", estimated value $6.5M. Total referrals: 1, total value: $6.5M.
```

**Test 27:**
```
The agent acknowledges the request and escalates to a human specialist. Response should indicate transfer is in progress.
```

**Test 28:**
```
The agent acknowledges the request and escalates to a human representative. Response should be empathetic and indicate transfer.
```

**Test 29:**
```
The agent politely declines the weather question and redirects to wealth advisory topics, listing available capabilities.
```

**Test 30:**
```
The agent explains it cannot provide stock prices and redirects to wealth advisory topics, listing available capabilities.
```

**Test 31:**
```
Response includes Johnson Family household with $2.8M AUM, Moderate risk, Alex Morgan advisor, members Sarah Johnson (Primary) and Tom Johnson (Spouse), and accounts Johnson IRA ($450K), Johnson 401k ($820K), Johnson Family Trust ($1.53M). Must handle plural "Johnsons" correctly.
```

**Test 32:**
```
Response shows Carlos Martinez financial goals: Retirement (target $1.5M, current $1.2M, 80.0% progress, $300K gap) and Vacation Home (target $350K, current $120K, 34.3% progress, $230K gap). Must resolve first-name-only "Carlos" to Carlos Martinez.
```

---

## 7. Evaluation Results Template

### Summary Table

Use this table to record results from actual evaluation runs. Pre-filled with all 32 test queries; score columns are blank for actual runs.

| Test # | Query | Topic | Action | Topic Match | Action Match | Data Acc. | Complete | Relevant | Tone | Action. | Error | Overall | Pass |
|--------|-------|-------|--------|:-----------:|:------------:|:---------:|:--------:|:--------:|:----:|:-------:|:-----:|:-------:|:----:|
| 1 | Tell me about the Johnson household | client_lookup | get_client_360 | | | | | | | | | | |
| 2 | Tell me about the Chen family | client_lookup | get_client_360 | | | | | | | | | | |
| 3 | Tell me about the Martinez household | client_lookup | get_client_360 | | | | | | | | | | |
| 4 | Tell me about the Patel family | client_lookup | get_client_360 | | | | | | | | | | |
| 5 | Tell me about the Williams family | client_lookup | get_client_360 | | | | | | | | | | |
| 6 | How is Wei Chen's portfolio? | portfolio_review | get_portfolio_summary | | | | | | | | | | |
| 7 | How is Raj Patel's portfolio performing? | portfolio_review | get_portfolio_summary | | | | | | | | | | |
| 8 | Show me James Williams portfolio | portfolio_review | get_portfolio_summary | | | | | | | | | | |
| 9 | What are the Johnsons' retirement goals? | goal_planning | get_financial_goals | | | | | | | | | | |
| 10 | What are the Patels' goals? | goal_planning | get_financial_goals | | | | | | | | | | |
| 11 | What goals does Carlos Martinez have? | goal_planning | get_financial_goals | | | | | | | | | | |
| 12 | Prep me for my meeting with Sarah Johnson | meeting_prep | get_meeting_prep | | | | | | | | | | |
| 13 | Prep me for my meeting with Carlos | meeting_prep | get_meeting_prep | | | | | | | | | | |
| 14 | Prepare my meeting with Raj Patel | meeting_prep | get_meeting_prep | | | | | | | | | | |
| 15 | Does Sarah Johnson need rebalancing? | rebalancing_alerts | check_rebalancing | | | | | | | | | | |
| 16 | Check rebalancing for Wei Chen | rebalancing_alerts | check_rebalancing | | | | | | | | | | |
| 17 | Does the Martinez account need rebalancing? | rebalancing_alerts | check_rebalancing | | | | | | | | | | |
| 18 | Show me recent transactions for Sarah Johnson | transaction_history | get_transactions | | | | | | | | | | |
| 19 | What are Wei Chen's latest transactions? | transaction_history | get_transactions | | | | | | | | | | |
| 20 | Show me Raj Patel's transaction history | transaction_history | get_transactions | | | | | | | | | | |
| 21 | Is the Patel account compliant? | compliance_check | run_compliance | | | | | | | | | | |
| 22 | Run a compliance check on the Martinez household | compliance_check | run_compliance | | | | | | | | | | |
| 23 | Check compliance for Wei Chen | compliance_check | run_compliance | | | | | | | | | | |
| 24 | Who referred the Williams family? | referral_tracking | get_referrals | | | | | | | | | | |
| 25 | Who referred the Johnsons? | referral_tracking | get_referrals | | | | | | | | | | |
| 26 | What's the referral source for the Patels? | referral_tracking | get_referrals | | | | | | | | | | |
| 27 | Transfer me to a specialist | escalation | (escalate) | | | N/A | | | | | | | |
| 28 | I need to speak to a human | escalation | (escalate) | | | N/A | | | | | | | |
| 29 | What is the weather today? | off_topic | (redirect) | | | N/A | | | | | | | |
| 30 | What's the stock price of Apple? | off_topic | (redirect) | | | N/A | | | | | | | |
| 31 | Tell me about the Johnsons | client_lookup | get_client_360 | | | | | | | | | | |
| 32 | How is Carlos doing on his goals? | goal_planning | get_financial_goals | | | | | | | | | | |

### Aggregate Metrics Template

```
=== EVALUATION RUN: [DATE] ===

Test Suite: WA_P1to5_Advisor_Full_Test
Agent: WA_P1to5_Advisor
LLM Judge: [GPT-4 / Claude / etc.]

RESULTS:
  Total Tests:     32
  Topic Match:     __/32 (__%)
  Action Match:    __/32 (__%)
  LLM Judge Pass:  __/32 (__%)

DIMENSION AVERAGES (across all 32 tests):
  Data Accuracy:   __/5.0
  Completeness:    __/5.0
  Relevance:       __/5.0
  Tone:            __/5.0
  Actionability:   __/5.0
  Error Handling:  __/5.0
  Overall:         __/5.0

QUALITY TIER: [Excellent / Good / Needs Work / Poor]

BY TOPIC:
  client_lookup (6 tests):     __/5.0 avg
  portfolio_review (3 tests):  __/5.0 avg
  goal_planning (3 tests):     __/5.0 avg
  meeting_prep (3 tests):      __/5.0 avg
  rebalancing (3 tests):       __/5.0 avg
  transactions (3 tests):      __/5.0 avg
  compliance (3 tests):        __/5.0 avg
  referrals (3 tests):         __/5.0 avg
  escalation (2 tests):        __/5.0 avg
  off_topic (2 tests):         __/5.0 avg

FAILURES:
  [List any tests that failed with reasons]

RECOMMENDATIONS:
  [Improvement suggestions based on lowest-scoring dimensions]
```

---

## Appendix A: Seed Data Quick Reference

### Households

| Household | AUM | Risk | Advisor | Members | Accounts |
|-----------|-----|------|---------|---------|----------|
| Johnson Family | $2.8M | Moderate | Alex Morgan | Sarah (Primary), Tom (Spouse) | IRA $450K, 401k $820K, Trust $1.53M |
| Chen Family | $4.1M | Aggressive | Alex Morgan | Wei (Primary), Lin (Spouse) | Brokerage $2.2M, Roth IRA $850K, 529 $1.05M |
| Martinez Family | $1.2M | Conservative | Alex Morgan | Carlos (Primary), Maria (Spouse) | IRA $680K, 401k $520K |
| Patel Family | $6.5M | Moderate | Alex Morgan | Raj (Primary), Priya (Spouse) | Brokerage $3.2M, Trust $2.1M, Roth IRA $1.2M |
| Williams Family | $890K | Growth | Alex Morgan | James (Primary), Olivia (Spouse) | 401k $520K, IRA $370K |

### Account Allocations

| Account | Allocation | YTD Return | Owner |
|---------|-----------|------------|-------|
| Johnson IRA | 60/30/10 | 7.2% | Sarah |
| Johnson 401k | 70/25/5 | 8.5% | Tom |
| Johnson Family Trust | 50/40/10 | 5.8% | Sarah |
| Chen Brokerage | 80/15/5 | 12.3% | Wei |
| Chen Roth IRA | 75/20/5 | 11.1% | Wei |
| Chen 529 Plan | 65/30/5 | 9.4% | Lin |
| Martinez IRA | 40/50/10 | 4.1% | Carlos |
| Martinez 401k | 35/55/10 | 3.8% | Maria |
| Patel Brokerage | 65/25/10 | 9.7% | Raj |
| Patel Trust | 55/35/10 | 6.9% | Raj |
| Patel Roth IRA | 60/30/10 | 7.8% | Priya |
| Williams 401k | 70/20/10 | 10.2% | James |
| Williams IRA | 65/25/10 | 8.9% | Olivia |

### Goals

| Goal | Client | Target | Current | Progress | Gap | Date |
|------|--------|--------|---------|----------|-----|------|
| Retirement | Sarah Johnson | $3.0M | $2.8M | 93.3% | $200K | 2035-01-01 |
| College Fund - Emma | Sarah Johnson | $200K | $145K | 72.5% | $55K | 2030-09-01 |
| Early Retirement | Wei Chen | $5.0M | $4.1M | 82.0% | $900K | 2032-06-01 |
| College Fund - Kids | Lin Chen | $400K | $1.05M | 262.5% | -$650K | 2034-09-01 |
| Retirement | Carlos Martinez | $1.5M | $1.2M | 80.0% | $300K | 2038-01-01 |
| Vacation Home | Carlos Martinez | $350K | $120K | 34.3% | $230K | 2029-06-01 |
| Retirement | Raj Patel | $8.0M | $6.5M | 81.3% | $1.5M | 2033-01-01 |
| Philanthropy Fund | Raj Patel | $1.0M | $650K | 65.0% | $350K | 2030-12-31 |
| Retirement | James Williams | $1.2M | $890K | 74.2% | $310K | 2040-01-01 |
| Home Down Payment | James Williams | $150K | $85K | 56.7% | $65K | 2027-06-01 |

### Referrals

| Household | Referral Name | Source | Type | Date | Status | Value |
|-----------|--------------|--------|------|------|--------|-------|
| Johnson | Johnson Referral | Dr. Robert Kim | Client | 2023-03-15 | Converted | $2.8M |
| Chen | Chen Referral | TechVentures Annual Gala | Event | 2022-11-08 | Converted | $4.1M |
| Martinez | Martinez Referral | First National Bank - Maria Lopez | Partner | 2024-01-20 | Contacted | $1.5M |
| Patel | Patel Referral | Sarah Johnson | Client | 2021-06-10 | Converted | $6.5M |
| Williams | Williams Referral | LinkedIn Campaign Q4 | Marketing | 2024-10-05 | New | $1.2M |

### Transaction Summary by Client

| Client | # Txns | Total Buys | Total Sells | Total Dividends | Total Fees | Net Activity |
|--------|--------|-----------|-------------|-----------------|------------|-------------|
| Sarah Johnson | 7 | $75K | $45K | $4.75K | $125 | -$25,375 |
| Tom Johnson | 3 | $15K | $0 | $0 | $0 | -$15,000 |
| Wei Chen | 9 | $210K | $150K | $7.6K | $550 | -$52,950 |
| Lin Chen | 2 | $20K | $0 | $0 | $0 | -$20,000 |
| Carlos Martinez | 5 | $27K | $8K | $2.8K | $170 | -$16,370 |
| Maria Martinez | 3 | $7K | $0 | $1.1K | $0 | -$5,900 |
| Raj Patel | 9 | $350K | $265K | $12.2K | $800 | -$73,600 |
| Priya Patel | 3 | $14K | $0 | $1.8K | $0 | -$12,200 |
| James Williams | 5 | $12K | $0 | $650 | $130 | -$11,480 |
| Olivia Williams | 6 | $18K | $5K | $450 | $92 | -$12,642 |

> **Net Activity formula:** Sells + Dividends - Buys - Fees (positive = net inflow, negative = net outflow)

---

## Appendix B: Drift Calculations Reference

### Rebalancing Drift (threshold: > 5%)

**Sarah Johnson (Moderate: 55/35/10):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Flagged? |
|---------|-------------|-------------|------------|----------|
| Johnson IRA (60/30/10) | +5% | -5% | 0% | No (at threshold, not exceeding) |
| Johnson Family Trust (50/40/10) | -5% | +5% | 0% | No (at threshold, not exceeding) |
| **Overall** | | | | **No rebalancing needed** |

**Wei Chen (Aggressive: 80/15/5):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Flagged? |
|---------|-------------|-------------|------------|----------|
| Chen Brokerage (80/15/5) | 0% | 0% | 0% | No (on target) |
| Chen Roth IRA (75/20/5) | -5% | +5% | 0% | No (at threshold) |
| **Overall** | | | | **No rebalancing needed** |

**Carlos Martinez (Conservative: 30/60/10):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Flagged? |
|---------|-------------|-------------|------------|----------|
| Martinez IRA (40/50/10) | +10% ⚠️ | -10% ⚠️ | 0% | Yes (2 flags) |
| **Overall** | | | | **Rebalancing recommended** |

### Compliance Drift (threshold: > 15%)

**Patel Family (Moderate: 55/35/10):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Suitability | Concentration | Pass? |
|---------|-------------|-------------|------------|-------------|---------------|-------|
| Patel Brokerage (65/25/10) | 10% | 10% | 0% | 65% < 70% ✓ | None > 80% ✓ | ✅ |
| Patel Trust (55/35/10) | 0% | 0% | 0% | 55% < 70% ✓ | None > 80% ✓ | ✅ |
| Patel Roth IRA (60/30/10) | 5% | 5% | 0% | 60% < 70% ✓ | None > 80% ✓ | ✅ |
| **Overall** | | | | | | **PASS** |

**Martinez Family (Conservative: 30/60/10):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Suitability | Concentration | Pass? |
|---------|-------------|-------------|------------|-------------|---------------|-------|
| Martinez IRA (40/50/10) | 10% | 10% | 0% | 40% < 50% ✓ | None > 80% ✓ | ✅ |
| Martinez 401k (35/55/10) | 5% | 5% | 0% | 35% < 50% ✓ | None > 80% ✓ | ✅ |
| **Overall** | | | | | | **PASS** |

**Chen Family (Aggressive: 80/15/5):**
| Account | Equity Drift | Fixed Drift | Cash Drift | Suitability | Concentration | Pass? |
|---------|-------------|-------------|------------|-------------|---------------|-------|
| Chen Brokerage (80/15/5) | 0% | 0% | 0% | N/A | 80% = threshold ✓ | ✅ |
| Chen Roth IRA (75/20/5) | 5% | 5% | 0% | N/A | None > 80% ✓ | ✅ |
| Chen 529 Plan (65/30/5) | 15% | 15% | 0% | N/A | None > 80% ✓ | ✅ |
| **Overall** | | | | | | **PASS** |

> **Key threshold distinctions:**
> - Rebalancing: `Math.abs(drift) > 5` — exactly 5% is WITHIN tolerance
> - Compliance drift: `drift > 15` — exactly 15% is WITHIN compliance
> - Concentration: `component > 80` — exactly 80% is NOT a violation
> - Suitability: Conservative equity max 50%, Moderate equity max 70%

# End-to-End Test Results — New Org Deployment

Org: `orgfarm-035b70d101` (fresh Agentforce Developer Edition)
Date: 2026-04-03

---

## Project 1: Hello World Agent

| # | Action | Input | Result | Response |
|---|--------|-------|--------|----------|
| 1.1 | HelloAction | "Sam" | PASS ✅ | Hello Sam! Welcome! I'm your Hello World agent. How can I help you today? |
| 1.2 | HelloAction | "" | PASS ✅ | Hello there! Welcome! I'm your Hello World agent. What can I do for you? |

---

## Project 2: WA CRM (SOQL-based)

| # | Action | Input | Result | Response |
|---|--------|-------|--------|----------|
| 2.1 | ClientLookupAction | "Johnson" | PASS ✅ | Johnson Family, $2.8M, Moderate, 2 members, 3 accounts |
| 2.2 | ClientLookupAction | "Wei Chen" | PASS ✅ | Wei Chen (Primary), Chen Family, $4.1M |
| 2.3 | ClientLookupAction | "Nonexistent" | PASS ✅ | No client or household found |
| 2.4 | PortfolioReviewAction | "Wei Chen" | PASS ✅ | $3.0M total, 11.97% YTD |
| 2.5 | PortfolioReviewAction | "Raj Patel" | PASS ✅ | $5.3M total, 8.59% YTD |
| 2.6 | GoalPlanningAction | "Patel" | PASS ✅ | Philanthropy 65%, Retirement 81.2% |
| 2.7 | GoalPlanningAction | "Carlos Martinez" | FAIL ❌ | Fuzzy match strips "s" from Martinez → no match |
| 2.8 | MeetingPrepAction | "Carlos" | PASS ✅ | Martinez Family, meeting Apr 6 |
| 2.9 | MeetingPrepAction | "Sarah Johnson" | FAIL ❌ | Fuzzy match strips "s" from Johnson → no match |

---

## Projects 3 & 4: WA Data Cloud (CdpQuery-based)

| # | Action | Input | Result | Response |
|---|--------|-------|--------|----------|
| 3.1 | DC_ClientLookupAction | "Johnson" | PASS ✅ | Johnson Family, $2.8M, Moderate, 2 members |
| 3.2 | DC_ClientLookupAction | "Wei Chen" | PASS ✅ | Chen Family, $4.1M, Aggressive, 2 members + accounts |
| 3.3 | DC_PortfolioReviewAction | "Sarah Johnson" | PASS ✅ | Johnson Family Trust $1.5M, IRA $450K, 401k $820K |
| 3.4 | DC_GoalPlanningAction | "Patel" | PASS ✅ | Philanthropy 65% ($650K/$1.0M), Retirement 81.2% ($6.5M/$8.0M) |
| 3.5 | DC_MeetingPrepAction | "Carlos" | PASS ✅ | Martinez Family, $1.2M, Conservative, Retirement Planning Check-in |
| 3.6 | DC_RebalancingAction | "Sarah Johnson" | PASS ✅ | Johnson Family, Moderate, Target 55/35/10, drift analysis per account |
| 3.7 | DC_TransactionHistoryAction | "Wei Chen" | PASS ✅ | 9 transactions: NVDA $100K, QQQ $35K, TSLA $75K... |
| 3.8 | DC_ComplianceCheckAction | "Patel" | PASS ✅ | Patel Family, Moderate, Target 55/35/10, account-level checks |
| 3.9 | DC_ReferralTrackingAction | "Williams" | PASS ✅ | LinkedIn Campaign Q4, Marketing, 2024-10-05, New, $1.2M |

---

## Summary

| Project | Tests | Passed | Failed | Pass Rate |
|---------|-------|--------|--------|-----------|
| 1 (Hello World) | 2 | 2 | 0 | 100% |
| 2 (WA CRM / SOQL) | 7 | 5 | 2 | 71% |
| 3+4 (WA Data Cloud) | 9 | 9 | 0 | 100% |
| **Total** | **18** | **16** | **2** | **89%** |

### Failure Analysis

Tests 2.7 and 2.9 fail due to a known regex bug in Project 2's SOQL-based actions. The `cleanName` regex `.replaceAll('(?i)s$', '')` strips the trailing "s" from names like "Martinez" and "Johnson", breaking the LIKE search. Project 4's hardened DC_* actions fix this with multi-level fallback and smarter regex — which is why the same queries ("Sarah Johnson", "Carlos") pass in the DC_* tests.

### Data Cloud Verification

| DLM Object | Records | Expected | Status |
|------------|---------|----------|--------|
| WA_Household_c_Home__dlm | 5 | 5 | ✅ |
| WA_Client_c_Home__dlm | 10 | 10 | ✅ |
| WA_Financial_Account_c_Home__dlm | 13 | 13 | ✅ |
| WA_Financial_Goal_c_Home__dlm | 10 | 10 | ✅ |
| WA_Meeting_c_Home__dlm | 5 | 5 | ✅ |
| WA_Transaction_c_Home__dlm | 52 | 52 | ✅ |
| WA_Referral_c_Home__dlm | 5 | 5 | ✅ |

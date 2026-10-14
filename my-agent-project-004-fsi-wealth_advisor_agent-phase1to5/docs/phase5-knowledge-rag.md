# Phase 5A: Knowledge Articles + RAG — Implementation Guide

## Overview

This guide covers setting up a Salesforce Knowledge base with FSI-specific articles and configuring Retrieval-Augmented Generation (RAG) so the WA_P1to5_Advisor agent can answer policy and procedure questions grounded in firm documentation.

**What This Enables:**
- "What's our firm's policy on margin accounts?"
- "What are the rebalancing guidelines?"
- "Walk me through the client onboarding process"

**Prerequisites:**
- Salesforce Knowledge enabled in your org
- WA_P1to5_Advisor agent deployed and active
- Einstein Search / Data Cloud Search Index configured

---

## Step 1: Enable Salesforce Knowledge

1. **Setup → Knowledge Settings**
2. Toggle **Salesforce Knowledge** to **Enabled**
3. Configure:
   - **Default Knowledge User:** Check the box for your admin profile
   - **Article Types:** Use the default `Knowledge__kav` or create a custom type
4. **Setup → Knowledge → Data Categories**
   - Create a category group: `Wealth_Management`
   - Add categories:
     - `Policies`
     - `Procedures`
     - `Compliance`
     - `Products`
     - `Client_Services`

## Step 2: Create Knowledge Articles

Import the following articles into Salesforce Knowledge. Each article below is provided as markdown content — create them via the Knowledge tab in Salesforce or use the Data Import Wizard.

---

### Article 1: Margin Account Policy

**Title:** Margin Account Policy
**URL Name:** margin-account-policy
**Category:** Policies
**Summary:** Firm policy governing margin account eligibility, limits, and maintenance requirements.

**Body:**

```
MARGIN ACCOUNT POLICY
Effective Date: January 1, 2024
Last Reviewed: June 15, 2024
Policy Owner: Chief Compliance Officer

1. ELIGIBILITY
   - Minimum account value: $250,000
   - Client must have "Aggressive" or "Very Aggressive" risk profile
   - Client must sign Margin Agreement and Risk Disclosure
   - Retirement accounts (IRA, 401k) are NOT eligible for margin

2. MARGIN LIMITS
   - Initial margin requirement: 50% of purchase price
   - Maintenance margin: 30% of current market value
   - Maximum margin utilization: 50% of account equity
   - Concentrated positions (>25% in single security): margin limited to 30%

3. MARGIN CALLS
   - Triggered when equity falls below maintenance margin (30%)
   - Client has 3 business days to deposit funds or liquidate positions
   - If unmet after 3 days, firm may liquidate positions at discretion
   - Advisor must be notified of all margin calls within 1 hour

4. PROHIBITED ACTIVITIES
   - No margin on penny stocks (< $5/share)
   - No margin on IPO shares for first 30 days
   - No margin on options positions without separate options approval
   - No margin lending to related parties

5. ADVISOR RESPONSIBILITIES
   - Review margin utilization monthly for all margin accounts
   - Document client understanding of margin risks annually
   - Report margin utilization >40% to compliance within 24 hours
   - Escalate any margin call to team lead immediately
```

---

### Article 2: Rebalancing Guidelines

**Title:** Portfolio Rebalancing Guidelines
**URL Name:** rebalancing-guidelines
**Category:** Procedures
**Summary:** Guidelines for when and how to rebalance client portfolios to maintain target allocations.

**Body:**

```
PORTFOLIO REBALANCING GUIDELINES
Effective Date: March 1, 2024
Last Reviewed: June 15, 2024

1. REBALANCING TRIGGERS
   Rebalancing is required when ANY of the following occur:
   - Asset class drift exceeds 5% from target allocation
   - Quarterly review (Jan, Apr, Jul, Oct — first week)
   - Significant life event (marriage, retirement, inheritance)
   - Risk profile change
   - Market correction >10% in any asset class

2. REBALANCING METHODS
   a. Calendar-based: Review all accounts quarterly
   b. Threshold-based: Trigger when drift >5% (preferred)
   c. Hybrid: Quarterly review + threshold monitoring (recommended)

3. TAX CONSIDERATIONS
   - Prefer rebalancing in tax-advantaged accounts (IRA, 401k) first
   - In taxable accounts, use tax-loss harvesting opportunities
   - Avoid short-term capital gains — hold positions >12 months when possible
   - Document tax impact analysis before executing trades >$50,000

4. EXECUTION PROCESS
   Step 1: Generate rebalancing report (current vs target allocation)
   Step 2: Identify trades needed to return to target
   Step 3: Review tax implications
   Step 4: Get client approval for trades >$100,000
   Step 5: Execute trades (batch during market hours 10am-3pm ET)
   Step 6: Confirm execution and update client record
   Step 7: Log rebalancing activity in compliance system

5. ALLOCATION TARGETS BY RISK PROFILE
   Conservative:  60% Fixed Income, 30% Equities, 5% Alternatives, 5% Cash
   Moderate:      35% Fixed Income, 50% Equities, 10% Alternatives, 5% Cash
   Aggressive:    15% Fixed Income, 65% Equities, 15% Alternatives, 5% Cash
   Very Aggressive: 5% Fixed Income, 75% Equities, 15% Alternatives, 5% Cash

6. DOCUMENTATION
   - All rebalancing decisions must be documented in the client file
   - Include: reason for rebalance, trades executed, tax impact, client approval
   - Retain records for minimum 7 years (SEC requirement)
```

---

### Article 3: Client Onboarding Procedures

**Title:** Client Onboarding Procedures
**URL Name:** client-onboarding-procedures
**Category:** Procedures
**Summary:** Step-by-step process for onboarding new wealth management clients.

**Body:**

```
CLIENT ONBOARDING PROCEDURES
Effective Date: February 1, 2024
Last Reviewed: May 30, 2024

1. INITIAL CONSULTATION (Day 1)
   - Schedule 60-minute discovery meeting
   - Gather: income, assets, liabilities, insurance, estate plans
   - Discuss: goals, time horizons, risk tolerance
   - Provide: ADV Part 2 brochure, privacy policy, fee schedule

2. DOCUMENTATION (Days 2-5)
   Required documents:
   - Signed Investment Advisory Agreement
   - Risk Tolerance Questionnaire (completed and scored)
   - KYC (Know Your Customer) form
   - W-9 / W-8BEN (tax identification)
   - Government-issued photo ID (copy)
   - Proof of address (utility bill or bank statement, <90 days)
   - Trust documents (if applicable)
   - Power of Attorney (if applicable)

3. ACCOUNT SETUP (Days 3-7)
   - Create household record in Salesforce (WA_Household__c)
   - Create client records (WA_Client__c) for all household members
   - Open custodial accounts (brokerage, IRA, trust as needed)
   - Set up beneficiary designations
   - Configure online access and reporting preferences

4. COMPLIANCE REVIEW (Days 5-10)
   - Compliance team reviews all documentation
   - AML (Anti-Money Laundering) screening
   - PEP (Politically Exposed Person) check
   - Suitability assessment: risk profile vs proposed allocation
   - Compliance sign-off required before first trade

5. INVESTMENT IMPLEMENTATION (Days 10-15)
   - Develop Investment Policy Statement (IPS)
   - Present proposed allocation to client
   - Get written approval
   - Execute initial trades
   - Confirm positions and send welcome portfolio report

6. ONGOING SERVICE SETUP (Days 15-30)
   - Schedule first quarterly review (90 days out)
   - Set up automated reporting (monthly statements)
   - Add to rebalancing monitoring system
   - Introduce to support team
   - Send welcome package (physical or digital)

7. MINIMUM ACCOUNT REQUIREMENTS
   - Individual accounts: $100,000 minimum
   - Household accounts: $250,000 minimum
   - Institutional accounts: $1,000,000 minimum
   - Fee waiver available for employees and immediate family
```

---

### Article 4: Risk Assessment Framework

**Title:** Risk Assessment Framework
**URL Name:** risk-assessment-framework
**Category:** Compliance
**Summary:** Framework for assessing and categorizing client risk tolerance and investment suitability.

**Body:**

```
RISK ASSESSMENT FRAMEWORK
Effective Date: January 15, 2024
Last Reviewed: June 1, 2024

1. RISK PROFILE CATEGORIES
   a. Conservative
      - Primary goal: Capital preservation
      - Time horizon: <5 years or income-dependent
      - Loss tolerance: <10% annual drawdown
      - Typical client: Retirees, near-retirees, risk-averse

   b. Moderate
      - Primary goal: Balanced growth and income
      - Time horizon: 5-15 years
      - Loss tolerance: 10-20% annual drawdown
      - Typical client: Mid-career professionals, dual-income households

   c. Aggressive
      - Primary goal: Capital appreciation
      - Time horizon: 15+ years
      - Loss tolerance: 20-35% annual drawdown
      - Typical client: Young professionals, high earners, long horizon

   d. Very Aggressive
      - Primary goal: Maximum growth
      - Time horizon: 20+ years
      - Loss tolerance: >35% annual drawdown
      - Typical client: Young investors, entrepreneurs, high net worth

2. RISK QUESTIONNAIRE SCORING
   - 20 questions, each scored 1-5
   - Total score ranges:
     20-40: Conservative
     41-60: Moderate
     61-80: Aggressive
     81-100: Very Aggressive
   - Questionnaire must be completed at onboarding and reviewed annually

3. SUITABILITY RULES
   - Client's investment allocation MUST match their risk profile
   - Deviations require: written client request + compliance approval
   - Maximum deviation: one category (e.g., Moderate client can request Aggressive)
   - Two-category deviations (e.g., Conservative → Aggressive): PROHIBITED

4. RISK PROFILE CHANGES
   - Client can request a risk profile change at any time
   - Requires: new questionnaire + advisor review + compliance sign-off
   - Downgrade (e.g., Aggressive → Moderate): effective immediately
   - Upgrade (e.g., Conservative → Aggressive): 5-day cooling-off period

5. SPECIAL CONSIDERATIONS
   - Clients age 70+: annual suitability review required
   - Concentrated positions (>25% single stock): additional risk disclosure
   - Margin accounts: only for Aggressive or Very Aggressive profiles
   - Options trading: separate approval process, minimum Aggressive profile
```

---

### Article 5: Fee Schedule

**Title:** Wealth Management Fee Schedule
**URL Name:** fee-schedule
**Category:** Products
**Summary:** Current fee schedule for wealth management advisory services.

**Body:**

```
WEALTH MANAGEMENT FEE SCHEDULE
Effective Date: January 1, 2024
Last Reviewed: April 1, 2024

1. ADVISORY FEES (Annual, billed quarterly in arrears)
   Assets Under Management (AUM)    Annual Fee
   ─────────────────────────────    ──────────
   First $500,000                    1.25%
   $500,001 - $1,000,000            1.00%
   $1,000,001 - $3,000,000          0.85%
   $3,000,001 - $5,000,000          0.75%
   $5,000,001 - $10,000,000         0.65%
   Over $10,000,000                  0.50% (negotiable)

   Fees are calculated on household AUM (all accounts combined).
   Blended rate applies across tiers.

2. FINANCIAL PLANNING FEES
   - Comprehensive Financial Plan: $2,500 (one-time)
   - Plan Update / Annual Review: $500
   - Retirement Income Analysis: $1,000
   - Estate Planning Review: $1,500
   - Tax Optimization Analysis: $750
   Planning fees may be waived for households with AUM >$2,000,000.

3. TRANSACTION COSTS (passed through at cost)
   - Equity trades: $0 (commission-free via custodian)
   - Mutual fund trades: $0 for NTF funds, $25 for transaction-fee funds
   - Bond trades: $1 per bond (minimum $25 per trade)
   - Options: $0.65 per contract
   - Wire transfers: $25 domestic, $50 international

4. ACCOUNT FEES
   - Account maintenance: $0 (waived for advisory clients)
   - Account transfer (ACAT out): $75
   - Account closure: $50
   - Paper statements: $5/month (electronic statements free)
   - Overnight check delivery: $25

5. DISCOUNTS
   - Employees and immediate family: 50% discount on advisory fees
   - Referral credit: $500 account credit per qualified referral
   - Multi-generational: 10% discount when 3+ generations are clients
   - Non-profit accounts: 25% discount on advisory fees

6. FEE BILLING
   - Fees calculated on prior quarter-end market value
   - Billed in arrears (end of each calendar quarter)
   - Deducted directly from investment account (default)
   - Invoice billing available upon request
   - Pro-rated for accounts opened/closed mid-quarter
```

---

## Step 3: Configure Search Index for RAG

For the agent to retrieve knowledge articles, you need a search index:

### Option A: Einstein Search (Recommended)

1. **Setup → Einstein Search → Enable Einstein Search**
2. **Setup → Einstein Search → Search Index**
   - Add `Knowledge__kav` to the search index
   - Fields to index: `Title`, `Summary`, `Body` (rich text)
   - Enable **Semantic Search** (vector embeddings)
3. Wait for initial indexing (can take 30-60 minutes)

### Option B: Data Cloud Search Index

1. **Data Cloud → Search Indexes → New**
2. Configure:
   - **Name:** WA Knowledge Index
   - **Source:** Knowledge__kav (via CRM Connector data stream)
   - **Fields:** Title, Summary, Body
   - **Embedding Model:** Einstein GPT Embeddings
   - **Chunk Size:** 500 tokens (recommended for policy documents)
   - **Overlap:** 50 tokens
3. **Save & Build Index**

### Option C: Einstein Knowledge Grounding (Simplest)

1. **Setup → Agentforce → Agent Settings → WA_P1to5_Advisor**
2. Under **Grounding Sources**, click **Add**
3. Select **Salesforce Knowledge**
4. Configure:
   - **Article Types:** Knowledge__kav
   - **Categories:** Wealth_Management (all subcategories)
   - **Max Articles Retrieved:** 3
   - **Relevance Threshold:** 0.7
5. **Save**

This is the simplest approach — the agent automatically searches Knowledge when it can't answer from its existing topics.

## Step 4: Agent Topic Definition — knowledge_base

Add this topic to the WA_P1to5_Advisor `.agent` file:

```yaml
topic knowledge_base:
    label: "Knowledge Base"
    description: "Answer questions about firm policies, procedures, compliance rules, and fee schedules using the knowledge base"

    actions:
        search_knowledge:
            description: "Search the firm's knowledge base for policies, procedures, guidelines, and fee information. Returns relevant article content."
            inputs:
                query: string
                    description: "The policy or procedure question"
            outputs:
                knowledgeResult: string
                    description: "Relevant knowledge article content"
            target: "apex://DC_KnowledgeSearchAction"

    reasoning:
        instructions:->
            if @variables.result:
                | Here is the relevant policy information:
                  {!@variables.result}
                  
                  Note: This information is from our firm's knowledge base. For the most current version, please check the compliance portal.
            else:
                | Use search_knowledge to find the relevant policy or procedure. Pass the user's question as the query.
        actions:
            search_knowledge: @actions.search_knowledge
                with query=...
                set @variables.result = @outputs.knowledgeResult
```

Add to the topic selector:

```yaml
go_to_knowledge_base: @utils.transition to @topic.knowledge_base
    description: "User wants to know about firm policies, procedures, fees, or compliance rules"
```

## Step 5: Apex Action for Knowledge Search (Optional)

If you want more control over the search than the built-in grounding provides:

```apex
public with sharing class DC_KnowledgeSearchAction {

    public class SearchInput {
        @InvocableVariable(label='Query' description='Policy or procedure question' required=true)
        public String query;
    }

    public class SearchOutput {
        @InvocableVariable(label='Knowledge Result' description='Relevant article content')
        public String knowledgeResult;
    }

    @InvocableMethod(label='Search Knowledge Base' description='Search firm knowledge base for policies and procedures')
    public static List<SearchOutput> searchKnowledge(List<SearchInput> inputs) {
        List<SearchOutput> outputs = new List<SearchOutput>();
        for (SearchInput input : inputs) {
            SearchOutput output = new SearchOutput();
            try {
                // Use SOSL to search Knowledge articles
                String searchQuery = 'FIND \'' + String.escapeSingleQuotes(input.query)
                    + '\' IN ALL FIELDS RETURNING Knowledge__kav(Title, Summary, Body__c WHERE PublishStatus = \'Online\' AND Language = \'en_US\') LIMIT 3';
                List<List<SObject>> results = Search.query(searchQuery);
                if (!results.isEmpty() && !results[0].isEmpty()) {
                    String response = '';
                    for (SObject article : results[0]) {
                        response += '📄 ' + (String) article.get('Title') + '\n';
                        response += (String) article.get('Summary') + '\n';
                        String body = (String) article.get('Body__c');
                        if (body != null && body.length() > 1000) {
                            body = body.substring(0, 1000) + '...';
                        }
                        response += body + '\n\n';
                    }
                    output.knowledgeResult = response;
                } else {
                    output.knowledgeResult = 'No knowledge articles found matching your query. Please contact the compliance team directly.';
                }
            } catch (Exception e) {
                output.knowledgeResult = 'Error searching knowledge base: ' + e.getMessage();
            }
            outputs.add(output);
        }
        return outputs;
    }
}
```

## Test Queries for knowledge_base Topic

| Query | Expected Article | Key Content |
|-------|-----------------|-------------|
| "What's our policy on margin accounts?" | Margin Account Policy | Eligibility, limits, margin calls |
| "When should I rebalance a portfolio?" | Rebalancing Guidelines | Triggers, methods, tax considerations |
| "Walk me through client onboarding" | Client Onboarding Procedures | 7-step process, documentation requirements |
| "What's the fee for a $2M account?" | Fee Schedule | 0.85% for $1M-$3M tier |
| "What risk profile allows margin?" | Risk Assessment Framework | Aggressive or Very Aggressive only |

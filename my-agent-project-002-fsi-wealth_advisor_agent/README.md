# FSI Wealth Advisor Agent

An Agentforce agent for wealth advisors that provides client lookups, portfolio reviews, goal planning, and meeting prep — powered by real CRM data.

## Quick Start

### Prerequisites
- Salesforce CLI (`sf`) installed
- An Agentforce-enabled org (trial or developer edition)
- Authenticated: `sf org login web --alias my-org`

### Deploy

```bash
# 1. Deploy custom objects and Apex classes
sf project deploy start --source-dir force-app

# 2. Grant field-level security (run once after first deploy)
sf apex run --file scripts/apex/grant-fls.apex

# 3. Seed demo data (5 households, 10 clients, 13 accounts, 10 goals, 5 meetings)
sf apex run --file scripts/apex/seed-data.apex

# 4. Deploy the agent script
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles

# 5. Open the org, find "WA Advisor v2" in Agents, assign user, Save, Commit Version
sf org open
```

### Activate
1. Go to Setup > Agents (or Agentforce Studio)
2. Click "WA Advisor v2"
3. Assign an EinsteinServiceAgent user
4. Click Save > Commit Version
5. The agent is now active

## Test Queries

Try these in the Agent Builder Preview or via chat:

### Client Lookup
- "Tell me about the Johnson household"
- "Who is Wei Chen?"
- "Look up the Patel family"

### Portfolio Review
- "How is Sarah Johnson's portfolio performing?"
- "Show me Wei Chen's allocation"
- "What are the returns for Raj Patel?"

### Goal Planning
- "What are the Johnsons' retirement goals?"
- "How is Carlos Martinez tracking on his goals?"
- "Show me the Patels' financial goals"

### Meeting Prep
- "Prep me for my meeting with Sarah Johnson"
- "What should I know before meeting Carlos Martinez?"
- "Give me a brief for the Patel meeting"

### Escalation
- "Transfer me to a specialist"
- "I need to speak to a human"

### Off Topic (should redirect)
- "What's the weather today?"
- "What's the stock price of Apple?"

## Demo Data

| Household | AUM | Risk | Members |
|-----------|-----|------|---------|
| Johnson | $2.8M | Moderate | Sarah (primary), Tom |
| Chen | $4.1M | Aggressive | Wei (primary), Lin |
| Martinez | $1.2M | Conservative | Carlos (primary), Maria |
| Patel | $6.5M | Moderate | Raj (primary), Priya |
| Williams | $890K | Growth | James (primary), Olivia |

## Architecture

```
User > Agent (WA_Advisor_v2) > Topic Selector
                                    |
        +-----------+-----------+-----------+--------+--------+
        v           v           v           v        v        v
   client_lookup  portfolio  goal_plan  meeting  escalation  off_topic
        |         review       |        prep        |
        v           v          v          v         v
   ClientLookup  Portfolio  GoalPlan  MeetingPrep  @utils
   Action.cls    Review     Action    Action.cls   .escalate
                 Action.cls .cls
        |           |          |          |
        +-----+-----+-----+---+
              v
         SOQL > Custom Objects
         (WA_Household__c, WA_Client__c,
          WA_Financial_Account__c,
          WA_Financial_Goal__c, WA_Meeting__c)
```

## Project Structure

```
force-app/main/default/
  aiAuthoringBundles/WA_Advisor_v2/   # Agent script (the only thing you deploy for the agent)
  classes/                             # 4 Apex actions
  objects/                             # 5 custom objects with fields
scripts/apex/
  seed-data.apex                       # Seeds 5 households with demo data
  grant-fls.apex                       # Grants field-level security
docs/
  architecture-option-a.md             # Full architecture diagram
```

# How Kiro Connects to Salesforce — Architecture & Toolchain

This document explains how an AI coding assistant (Kiro, powered by Claude Opus 4.6) was able to build, deploy, test, and brand 4 Salesforce Agentforce projects across 2 orgs — writing Apex, deploying metadata, seeding data, running agent tests, customizing Experience Cloud branding, and pushing to git — all from a single chat conversation.

---

## The Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌───────────┐     ┌──────────────┐     ┌────────────────────────────────┐ │
│  │           │     │              │     │                                │ │
│  │   KIRO    │────▶│  TERMINAL    │────▶│  SALESFORCE CLI (sf)           │ │
│  │  (Opus    │     │  (bash)      │     │  installed on your machine     │ │
│  │   4.6)    │     │              │     │                                │ │
│  └───────────┘     └──────────────┘     └──────────┬─────────────────────┘ │
│                                                    │                       │
│                                                    │ Uses your stored      │
│                                                    │ OAuth token           │
│                                                    │ from ~/.sf/           │
│                                                    ▼                       │
│                                         ┌────────────────────────────────┐ │
│                                         │  SALESFORCE ORG                │ │
│                                         │  (Metadata API, REST API,     │ │
│                                         │   Tooling API, Connect API)   │ │
│                                         └────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: The LLM (Claude Opus 4.6) — The Brain

The LLM is the reasoning engine. It provides:

- Knowledge of Salesforce APIs, metadata types, and XML formats
- Ability to write correct Apex code (SOQL, DML, ConnectApi, CdpQuery)
- Understanding of ExperienceBundle JSON structure (brandingSets, themes, views)
- Decision-making: which commands to run, in what order, and how to recover from errors
- Ability to read error messages, diagnose problems, and try alternative approaches
- Understanding of natural language ("I don't like this Capricorn Coffee thing" → modify branding)

Without the LLM, there is no intelligence. It would be a dumb script runner with no ability to adapt, troubleshoot, or create new code on the fly.

### What the LLM knows (from training data)

| Domain | Examples |
|--------|----------|
| Salesforce Metadata API | CustomObject XML, ApexClass, PermissionSet, ExperienceBundle, AiAuthoringBundle |
| Salesforce REST API | `/services/data/v66.0/sobjects/`, Connect API, Tooling API |
| Apex language | Classes, invocable methods, SOQL, DML, ConnectApi.CdpQuery, HttpCallout |
| Salesforce CLI | `sf project deploy`, `sf apex run`, `sf agent test run`, `sf community publish` |
| Experience Cloud | ExperienceBundle structure, brandingSets JSON, theme layouts, hero components |
| Data Cloud | CRM connectors, DLO streams, DMO mappings, Connect REST API for DMO creation |
| Git | Commit, push, branch management, credential scrubbing |

---

## Layer 2: Kiro (the IDE Agent) — The Hands

Kiro is the IDE that gives the LLM the ability to act on the real world. It provides tools:

| Tool | What It Does | How It Was Used |
|------|-------------|-----------------|
| `executeBash` | Run any shell command | `sf project deploy`, `sf apex run`, `curl`, `python3`, `git` |
| `fsWrite` | Create or overwrite files | Write Apex classes, XML metadata, JSON configs |
| `readFile` | Read file contents | Read ExperienceBundle JSON, deployment status, Apex code |
| `strReplace` | Edit files surgically | Update branding colors, fix metadata, modify docs |
| `grepSearch` | Search across codebase | Find specific metadata, locate config values |
| `webSearch` | Search the internet | Look up Salesforce docs, find API endpoints, research solutions |
| `webFetch` | Read web pages | Read Salesforce developer blog posts, Trailhead guides |

Without Kiro, the LLM can only talk. It cannot touch files, run commands, or interact with any system.

---

## Layer 3: Your Machine — The Bridge

The actual connection to Salesforce happens through tools installed on your local machine:

### Salesforce CLI (`sf`)

The primary interface. Handles authentication, metadata deployment, Apex execution, and agent testing.

```bash
# Deploy metadata (objects, classes, agents, permission sets)
sf project deploy start --source-dir force-app --target-org new-org

# Run Apex scripts (seed data, grant permissions, verify data)
sf apex run --file scripts/apex/seed-data.apex --target-org new-org

# Run agent tests (end-to-end through the agent)
sf agent test run --api-name WA_P1to5_Advisor_Full_Test --target-org new-org

# Publish Experience Cloud sites
sf community publish --name "Wealth Advisor Portal" --target-org new-org

# Retrieve ExperienceBundle for programmatic editing
sf project retrieve start --manifest package.xml --target-org new-org
```

### curl + Access Token (REST API)

For operations the CLI doesn't cover — updating Network objects, querying CommunitiesSettings, calling Connect API:

```bash
# Extract access token from sf CLI session
ACCESS_TOKEN=$(sf org display --target-org new-org --json | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['accessToken'])")

# Update Network name via REST API
curl -X PATCH -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"Name": "Wealth Advisor Portal"}' \
  "$INSTANCE_URL/services/data/v66.0/sobjects/Network/$COMMUNITY_ID"

# Query via Tooling API
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$INSTANCE_URL/services/data/v66.0/tooling/query/?q=SELECT+Metadata+FROM+CommunitiesSettings"
```

### python3 (JSON Processing & Scripting)

For complex operations like modifying ExperienceBundle JSON, creating DMO mappings via Connect API:

```python
# Modify ExperienceBundle branding programmatically
with open("brandingSets/helpCenter.json") as f:
    branding = json.load(f)
branding["values"]["ActionColor"] = "#1B5E20"
branding["values"]["CompanyLogo"] = ""  # Remove Capricorn Coffee
```

### SOQL Queries

For reading data from the org:

```bash
sf data query --query "SELECT Id, Name, Status FROM Network" --target-org new-org
```

---

## Layer 4 (Optional): MCP Connectors

MCP (Model Context Protocol) connectors were NOT used in this project, but they represent an alternative path to the same result.

### What we did (without MCP)

```
Kiro ──▶ executeBash("sf project deploy start ...") ──▶ Salesforce
Kiro ──▶ executeBash("curl -H 'Bearer ...' ...") ──▶ Salesforce
Kiro ──▶ executeBash("sf apex run --file ...") ──▶ Salesforce
```

### What MCP could do (hypothetical Salesforce MCP server)

```
Kiro ──▶ MCP tool: deploy_metadata(source_dir="force-app") ──▶ Salesforce
Kiro ──▶ MCP tool: run_soql("SELECT Id FROM Account") ──▶ Salesforce
Kiro ──▶ MCP tool: run_apex(file="seed-data.apex") ──▶ Salesforce
```

Same result, cleaner interface. MCP provides structured tool definitions with typed parameters instead of raw shell commands. It's most useful when:

- The CLI isn't installed or available
- You want structured, validated tool interfaces
- You're connecting to services that don't have a CLI (databases, third-party APIs)
- You want to add new capabilities without installing new CLI tools

### MCP in the Salesforce Agentforce context

MCP also appears in this project in a different role — as a way for the Agentforce agent (WA_P1to5_Advisor) to call external APIs:

```
End User ──▶ Agentforce Agent ──▶ MCP Connector ──▶ Alpha Vantage (market data)
                                                 ──▶ NewsAPI (financial news)
                                                 ──▶ Tavily (web search)
```

This is a different use of MCP — it's the Salesforce agent calling out to external services, not Kiro calling into Salesforce.

---

## The Key Insight

Kiro has no special Salesforce access. Everything it does, you could do by typing the same commands in your terminal. The combination that makes it powerful:

1. The LLM knows what to do (Salesforce domain knowledge)
2. Kiro can execute it (file I/O + shell commands)
3. The sf CLI bridges to Salesforce (using your OAuth session)
4. Your one-time `sf org login web` unlocked everything

If you run `sf org logout --target-org new-org`, all access is revoked instantly. No credentials are stored by Kiro.

---

## What Can Be Done Programmatically vs What Requires UI

| Programmatic (Kiro can do it) | UI Only (you must click) |
|-------------------------------|--------------------------|
| Deploy custom objects, fields, classes | Create Data Cloud streams (category picker) |
| Deploy agent bundles (AiAuthoringBundle) | Activate agents (assign user + commit version) |
| Deploy permission sets, remote sites | Enable features (Einstein toggle, ExperienceBundle checkbox) |
| Deploy CORS, CSP trusted sites | Configure AI Experiences (set Default AI Agent on site) |
| Run Apex scripts (seed data, grant FLS) | Enable Salesforce Knowledge |
| Run agent tests (`sf agent test run`) | Set OWD to Private |
| Retrieve + modify + deploy ExperienceBundle | Create Experience Cloud sites (initial creation) |
| Publish Experience Cloud sites | Install Salesforce for Slack |
| Query any object via SOQL | |
| Update records via REST API | |
| Push to git | |

---

## Prerequisites — What Made It Possible

| You Did | That Gave Kiro |
|---------|----------------|
| `sf org login web --alias new-org` | OAuth token stored in `~/.sf/` — all API access flows from this |
| Installed Salesforce CLI (`sf`) | `sf` commands available in shell (deploy, retrieve, query, apex) |
| Created SFDX project (`sfdx-project.json`) | Tells sf CLI where to find metadata to deploy |
| Had `curl` + `python3` on machine | REST API calls + JSON parsing for things sf CLI doesn't cover |
| Enabled ExperienceBundle Metadata API (checkbox) | Allowed programmatic retrieval and editing of site branding |

---

## What Was Built Using This Approach

| Project | What Was Deployed | Method |
|---------|-------------------|--------|
| 001 — Hello World Agent | 1 Apex class, 1 agent bundle | sf CLI |
| 002 — WA CRM (SOQL) | 5 objects, 4 Apex classes, seed data, agent | sf CLI + Apex scripts |
| 003 — WA Data Cloud | 4 DC_* Apex classes, agent, DMO mappings | sf CLI + Connect REST API (python3) |
| 004 — WA Phase 1-5 | 8 objects, 11 Apex classes, 3 perm sets, 3 remote sites, CORS, CSP, agent, 54 test cases, 90+ seed records, Experience Cloud branding | sf CLI + REST API + ExperienceBundle + python3 |

All 4 projects deployed to a fresh org, tested with 32-query agent test suite (96.88% topic, 87.50% action, 100% outcome), and pushed to git — from a single Kiro chat conversation.

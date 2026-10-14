# Agent Broker — Routing Verification

This document maps each routing policy from `agent-network.yaml` to the
`anypoint-cli-v4` command (and REST equivalent) that verifies it is
active in the deployed Agent Fabric network.

Network name: **fsi-investment-research-v3**
Expected registry size post-deploy: **7** (4 agents + 3 MCP servers)

## Setup

All commands assume:

```bash
export ANYPOINT_ORG_ID="<org-uuid>"
export ANYPOINT_ENV_ID="<env-uuid>"
export ANYPOINT_HOST="https://anypoint.mulesoft.com"
# anypoint-cli-v4 conf  (interactive) OR export ANYPOINT_ACCESS_TOKEN=<bearer>
```

REST base path (when the CLI sub-command is absent):

```
${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}
```

## Routing policies — overview

| # | Policy name              | Match (query patterns)                                             | Target agent                  | Model  |
|---|--------------------------|--------------------------------------------------------------------|-------------------------------|--------|
| 1 | `l1-l2-direct-tools`     | `price of *`, `quote for *`, `who covers *`, `latest 10-K *`, `news on *` | `ir-research-orchestrator` | haiku  |
| 2 | `l3-l4-analysis`         | `deep dive *`, `research brief *`, `DCF valuation *`, `fair value *`, `initiate coverage *` | `ir-research-orchestrator` + delegates to `financial-analysis-agent`, `sentiment-analysis-agent` | sonnet |
| 3 | `compliance-routing`     | `restricted list *`, `can I trade *`, `compliance check *`, `MNPI *` | `ir-compliance-agent`         | —      |

Default agent: `ir-research-orchestrator`.

---

## Rule 1 — `l1-l2-direct-tools`

Low-complexity lookups (L1/L2) stay in the orchestrator and call MCP tools
directly, running on Claude Haiku for minimal latency.

**CLI verification**

```bash
anypoint-cli-v4 agent-fabric routing describe \
    --network fsi-investment-research-v3 \
    --policy  l1-l2-direct-tools \
    --output  json
```

Expected `.route.agent == "ir-research-orchestrator"` and
`.route.model == "haiku"`.

**REST equivalent**

```bash
curl -sS \
  -H "Authorization: Bearer ${ANYPOINT_ACCESS_TOKEN}" \
  "${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}/agent-networks/fsi-investment-research-v3/routing/l1-l2-direct-tools" \
  | jq '.route'
```

**Smoke test** (dry-run, no side effects):

```bash
anypoint-cli-v4 agent-fabric routing simulate \
    --network fsi-investment-research-v3 \
    --query "price of NVDA"
```

Expected decision: `policy=l1-l2-direct-tools, agent=ir-research-orchestrator, model=haiku`.

---

## Rule 2 — `l3-l4-analysis`

Deep analysis (L3/L4) routes to the orchestrator on Claude Sonnet and
delegates to the Strands agents running on AWS Lambda.

**CLI verification**

```bash
anypoint-cli-v4 agent-fabric routing describe \
    --network fsi-investment-research-v3 \
    --policy  l3-l4-analysis \
    --output  json
```

Expected:
- `.route.model == "sonnet"`
- `.route.delegateTo` contains `financial-analysis-agent` AND `sentiment-analysis-agent`

**REST equivalent**

```bash
curl -sS \
  -H "Authorization: Bearer ${ANYPOINT_ACCESS_TOKEN}" \
  "${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}/agent-networks/fsi-investment-research-v3/routing/l3-l4-analysis" \
  | jq '.route | {model, delegateTo}'
```

**Smoke test**

```bash
anypoint-cli-v4 agent-fabric routing simulate \
    --network fsi-investment-research-v3 \
    --query "deep dive on NVDA fair value"
```

Expected decision: `policy=l3-l4-analysis, agent=ir-research-orchestrator,
model=sonnet, delegates=[financial-analysis-agent, sentiment-analysis-agent]`.

---

## Rule 3 — `compliance-routing`

Compliance queries skip the orchestrator entirely and go straight to the
dedicated compliance agent for restricted-list, MNPI, trading-window, and
concentration checks.

**CLI verification**

```bash
anypoint-cli-v4 agent-fabric routing describe \
    --network fsi-investment-research-v3 \
    --policy  compliance-routing \
    --output  json
```

Expected `.route.agent == "ir-compliance-agent"`.

**REST equivalent**

```bash
curl -sS \
  -H "Authorization: Bearer ${ANYPOINT_ACCESS_TOKEN}" \
  "${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}/agent-networks/fsi-investment-research-v3/routing/compliance-routing" \
  | jq '.route.agent'
```

**Smoke test**

```bash
anypoint-cli-v4 agent-fabric routing simulate \
    --network fsi-investment-research-v3 \
    --query "can I trade AAPL?"
```

Expected decision: `policy=compliance-routing, agent=ir-compliance-agent`.

---

## Registry membership check

```bash
anypoint-cli-v4 agent-fabric registry list \
    --organization "$ANYPOINT_ORG_ID" \
    --environment  "$ANYPOINT_ENV_ID" \
    --output json \
  | jq '[.[] | .id] | sort'
```

Expected exactly these 7 ids (sorted):

```json
[
  "financial-analysis-agent",
  "ir-compliance-agent",
  "ir-research-orchestrator",
  "market-data",
  "news-search",
  "sec-edgar",
  "sentiment-analysis-agent"
]
```

REST equivalent: `GET …/registry?type=all`.

---

## CLI fallback matrix

| Action              | Primary (anypoint-cli-v4)                          | Fallback (REST)                                         |
|---------------------|----------------------------------------------------|---------------------------------------------------------|
| Validate network    | `agent-fabric validate --file <yaml>`              | `POST /agent-networks/validate`                         |
| Deploy network      | `agent-fabric deploy --file <yaml>`                | `POST /agent-networks` (create) / `PUT /agent-networks/<name>` (update) |
| List registry       | `agent-fabric registry list`                       | `GET /registry?type=all`                                |
| Describe routing    | `agent-fabric routing describe --policy <name>`    | `GET /agent-networks/<name>/routing/<policy>`           |
| Simulate routing    | `agent-fabric routing simulate --query "<q>"`      | `POST /agent-networks/<name>/routing/simulate` body `{ "query": "<q>" }` |

> **Note**: `anypoint-cli-v4` sub-command names for Agent Fabric are
> subject to change between CLI releases. The deploy and test scripts in
> this directory auto-fall-back to REST when a sub-command is missing.

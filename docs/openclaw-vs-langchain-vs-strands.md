# OpenClaw vs LangChain vs Strands — Agent Framework Comparison

> Date: April 21, 2026
> Audience: Engineering leads, architects, decision-makers
> Purpose: Explain the structural difference between three agent frameworks with real code snippets from this repo

---

## The Three Philosophies

Think of agent frameworks as three different takes on how to build AI agents:

- **LangChain = Lego bricks.** A huge box of pieces you snap together in Python. Total flexibility, lots of glue code.
- **Strands = Clean SDK.** AWS's minimal decorator-based SDK. Lean, Bedrock-native, runs great on Lambda.
- **OpenClaw = Opinionated platform.** Everything in the box — channels, pipeline, memory, skills, learning.

## What Makes OpenClaw Different

1. **Channels come free.** Slack, WhatsApp, Telegram, Discord, web chat, iMessage — wired in via config. In LangChain or Strands, you write it yourself.
2. **Skills are markdown files, not code.** YAML frontmatter + plain-English instructions. Change behavior by editing a `.md` file, not redeploying code.
3. **Persistent per-user memory out of the box.** The agent remembers what you asked last week.
4. **AutoResearchClaw is bundled.** A 23-stage research pipeline with HITL gates, self-healing, anti-fabrication. Thousands of lines of orchestration you don't write.
5. **MetaClaw learns across runs.** Failures become new skills automatically.
6. **MCP-native.** Drop an MCP server URL into config, the agent can use its tools. No adapter code.

## The Tradeoff

- **LangChain** wins if you want total control and don't mind writing plumbing.
- **Strands** wins if you want a lightweight SDK and you're all-in on AWS Bedrock + Lambda.
- **OpenClaw** wins if you want a running system in days instead of months — but you accept its opinions about how agents should work.

**The catch with OpenClaw:** compiled enforcement (Python types, Apex runtime) becomes prompt-based enforcement (markdown instructions). Less code, but also less runtime guarantee. A clever input might bypass a prompt — harder to bypass compiled code. That's the real engineering tradeoff behind "config not code."

---

## Structural Comparison

### LangChain — "Wire everything yourself in Python"

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_aws import ChatBedrock
from langchain.memory import ConversationBufferMemory

@tool
def get_stock_quote(ticker: str) -> dict:
    """Get current quote for a ticker."""
    return alpha_vantage_client.quote(ticker)

@tool
def check_compliance(ticker: str) -> dict:
    """Check restricted list, MNPI, trading windows."""
    # 50 lines of SOQL + logic you write yourself
    ...

llm = ChatBedrock(model_id="anthropic.claude-sonnet-4-6")
memory = ConversationBufferMemory()
tools = [get_stock_quote, check_compliance]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an FSI research agent..."),  # you write the whole prompt
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, memory=memory)

# Slack? You build it. WhatsApp? You build it. Audit log? You build it.
# Pipeline with HITL gates? Weeks of work.
result = executor.invoke({"input": "Deep dive on NVDA"})
```

Imperative Python. You import pieces, wire them together, write prompts inline, manage memory, and handle every channel yourself.

---

### Strands — "AWS's clean SDK, decorator-based"

```python
from strands import Agent, tool
from strands.models import BedrockModel

@tool
def run_dcf(ticker: str) -> dict:
    """Run DCF valuation for a ticker."""
    return {"fair_value": 450.0, "upside": 0.12}

@tool
def get_quote(ticker: str) -> dict:
    """Get current market quote."""
    return alpha_vantage.quote(ticker)

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-6")

agent = Agent(
    model=model,
    tools=[run_dcf, get_quote],
    system_prompt="You are a financial analysis agent.",
)

# Deploy as Lambda handler
def lambda_handler(event, context):
    return agent(event["query"])
```

Even leaner than LangChain. `@tool` decorator, `Agent` class, done. But still no channels, no pipeline, no memory, no skills registry. Just the agent loop. In project 005, each Strands agent is its own Lambda function — you build the gateway, routing, and orchestration yourself.

---

### OpenClaw — "Everything is config and markdown"

Directory structure:

```
openclaw/
├── openclaw.json          ← one JSON file configures everything
├── AGENTS.md              ← agent personas (markdown)
├── IDENTITY.md            ← agent behavior rules
├── TOOLS.md               ← tool descriptions
├── channels/              ← Slack, WhatsApp, Telegram configs
├── skills/
│   ├── salesforce-crm/
│   │   ├── SKILL.md       ← YAML frontmatter + markdown instructions
│   │   └── *.py           ← optional Python helpers
│   ├── compliance-screening/
│   │   ├── SKILL.md
│   │   ├── screening.py
│   │   └── mnpi_filter.py
│   ├── financial-analysis/
│   ├── fsi-research/
│   └── audit-logging/
├── autoresearchclaw/      ← bundled 23-stage pipeline
└── metaclaw_lessons/      ← cross-run learning data
```

**Agent definition is JSON** (real snippet from project 006):

```json
{
  "agents": {
    "list": [{
      "id": "fsi-research",
      "name": "FSI Research Agent",
      "model": "amazon-bedrock/us.anthropic.claude-sonnet-4-6",
      "systemPromptOverride": "You are an FSI Equity Research Agent..."
    }]
  },
  "mcp": {
    "servers": {
      "sec-edgar":      { "transport": "stdio", "command": "node", "args": ["mcp-rest-bridge.mjs"] },
      "market-data":    { "transport": "stdio", "command": "node", "args": ["mcp-rest-bridge.mjs"] },
      "salesforce-crm": { "transport": "stdio", "command": "node", "args": ["mcp-rest-bridge.mjs"] }
    }
  },
  "channels": {},
  "hooks": { "enabled": true, "path": "/hooks" }
}
```

**A skill is a markdown file with YAML frontmatter** (real snippet from `openclaw/skills/compliance-screening/SKILL.md`):

```markdown
---
name: Compliance Screening
slug: compliance-screening
version: 1.0.0
description: FINRA compliance checks — restricted list, MNPI, trading windows.
trigger-keywords:
  - compliance
  - restricted
  - can I trade
  - MNPI
applicable-stages: [5, 9, 20, 22, 23]
metadata:
  requires:
    env:
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
---

# Compliance Screening

## Checks (run in order)

### 1. Restricted List Check
Query IR_Audit_Log__c for RESTRICTED_LIST_ADD entries:

curl "$SF_INSTANCE_URL/services/data/v66.0/query/?q=SELECT+..."

If result found: BLOCK the action. Log Compliance_Status__c = 'FAIL'.

### 2. MNPI Check
...
```

That's the whole skill. No Python class, no decorator, no registration call. The agent reads the SKILL.md, follows the instructions in natural language, and executes the bash/curl steps. The trigger keywords determine when it's relevant. The stage numbers tell the pipeline where to invoke it.

---

## Side-by-Side

| | LangChain | Strands | OpenClaw |
|---|-----------|---------|----------|
| How you define an agent | Python code with classes and prompts | `Agent()` constructor with `@tool` fns | JSON config + markdown system prompt |
| How you define a tool/skill | `@tool` decorator on a Python fn | `@tool` decorator on a Python fn | A folder with SKILL.md + optional .py helpers |
| How tools get registered | Pass a list to the agent | Pass a list to the agent | Auto-discovered from `skills/` folder |
| How you add Slack | You write Slack integration | You write Slack integration | Drop config in `channels/slack.json` |
| How you add a pipeline | You write the state machine | You write the state machine | Fork AutoResearchClaw, edit YAML |
| How you change behavior | Edit Python, redeploy | Edit Python, redeploy | Edit a markdown file |
| Compile-time enforcement | Strong (Python types) | Strong (Python types) | Weak (prompt-based) |
| Config-to-code ratio | 5% config, 95% code | 5% config, 95% code | 60% config, 40% code |

---

## Simple Analogy

- **LangChain** = IKEA — buy the parts, assemble yourself.
- **Strands** = a nice coffee table — solid, does one thing well.
- **OpenClaw** = a furnished apartment — move in and everything works, but you live with the landlord's taste.

---

## Proof Point From This Repo

The same compliance logic appears in both 005 and 006:

| Project | Implementation | Lines of code |
|---------|---------------|---------------|
| 005 (Agentforce) | 24 Apex classes | ~4,000 |
| 006 (OpenClaw) | SKILL.md files + small Python helpers | ~746 markdown + ~300 Python |

Same behavior. Different place. Code in 005, configuration in 006. That's the structural shift.

---

## Bottom Line

- **LangChain** = write code to do everything.
- **Strands** = write code, AWS does the hosting.
- **OpenClaw** = write markdown and JSON, OpenClaw does the rest.

Choose based on how much flexibility you need vs how fast you want to ship. If your team is comfortable writing agent infrastructure, LangChain or Strands give you control. If you want channels, pipeline, memory, and compliance gates on day one — OpenClaw's opinionated defaults save weeks of work, at the cost of runtime enforcement strength.

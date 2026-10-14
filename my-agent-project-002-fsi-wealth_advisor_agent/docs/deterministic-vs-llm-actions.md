# Deterministic vs LLM Action Execution in Agent Script

```
v2/v3/v4 (BROKEN - LLM decides whether to call action)
═══════════════════════════════════════════════════

User: "Tell me about the Johnsons"
  │
  ▼
Topic Selector ──▶ client_lookup
  │
  ▼
reasoning:
  instructions: ->
    | "ALWAYS call get_client_360..."     ◄── prompt text (LLM suggestion)
  actions:
    get_client_360: @actions.get_client_360
      with clientName=...                 ◄── LLM CHOOSES whether to call
  │
  ▼
LLM thinks: "I should ask for clarification first"
  │
  ▼
Response: "Could you provide their first names?"   ❌ NO DATA


v5 (FIX - deterministic run before LLM reasons)
═══════════════════════════════════════════════════

User: "Tell me about the Johnsons"
  │
  ▼
Topic Selector ──▶ client_lookup
  │
  ▼
TURN 1: reasoning:
  instructions: ->                        ◄── deterministic logic
    if not @variables.client_name_input:
      | "Ask for client name"             ◄── LLM asks for name
  actions:
    store_name: @utils.setVariables       ◄── LLM extracts "Johnson"
      with client_name_input=...              and stores it
  │
  ▼
LLM: "Which client?" / User provides name
  │
  ▼
TURN 2: reasoning:
  instructions: ->                        ◄── deterministic logic
    if @variables.client_name_input and not @variables.client_result:
      run @actions.get_client_360         ◄── DETERMINISTIC - MUST EXECUTE
        with clientName=@variables.client_name_input
        set @variables.client_result = @outputs.clientSummary
    │
    ▼ (action runs, data returned)
    │
    if @variables.client_result:
      | "Here is the client info:         ◄── prompt with REAL DATA
         {!@variables.client_result}"
  │
  ▼
LLM presents: "Johnson Family, $2.8M AUM, Sarah, Tom..."   ✅ REAL DATA


KEY DIFFERENCE:
═══════════════

  actions: block     = LLM optional (LLM decides)
  run @actions       = deterministic (code, always executes)
  inside instructions:->
```

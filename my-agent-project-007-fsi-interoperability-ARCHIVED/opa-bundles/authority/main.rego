# authority/main.rego — Core M2 Authority Rules
#
# Evaluates (identity, action, target, context) -> ALLOW/DENY/ESCALATE
# Default: DENY (fail-closed). No fallback. No degraded mode.
#
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package authority.main

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# DEFAULT: DENY (fail-closed)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Default deny
# description: All requests denied unless explicitly allowed
# custom:
#   wsp_section: "1.0"
default check_authority := {
    "decision": "DENY",
    "reason": "default deny — no matching allow rule",
    "rule": "authority/main.rego:default_deny",
    "wsp_section": "1.0",
}

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Explicit excludes — always deny first
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Check authority excludes
# description: Actions in authority_excludes are always denied
# custom:
#   wsp_section: "2.0"
check_authority := result if {
    some excluded in input.identity.authority_excludes
    action_matches(input.action, excluded)
    result := {
        "decision": "DENY",
        "reason": sprintf("Action '%s' is explicitly excluded", [input.action]),
        "rule": "authority/main.rego:check_excludes",
        "wsp_section": "2.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Pod isolation — Tier 5 HF Chinese wall enforcement
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Pod isolation check
# description: Tier 5 hedge fund pod boundary enforcement
# custom:
#   wsp_section: "2.0"
check_authority := result if {
    input.identity.archetype == "tier5_hedge_fund"
    input.identity.pod_id != null
    input.context.target_pod_id != null
    input.identity.pod_id != input.context.target_pod_id
    result := {
        "decision": "DENY",
        "reason": sprintf(
            "Pod isolation: actor pod '%s' cannot access pod '%s'",
            [input.identity.pod_id, input.context.target_pod_id],
        ),
        "rule": "authority/main.rego:check_pod_isolation",
        "wsp_section": "2.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 3: Client scope enforcement
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Client scope check
# description: Advisor can only access clients in their client_scope
# custom:
#   wsp_section: "2.0"
check_authority := result if {
    count(input.identity.client_scope) > 0
    target_client := object.get(input.context, "client_id", input.target_id)
    target_client != null
    not target_client in input.identity.client_scope
    result := {
        "decision": "DENY",
        "reason": sprintf(
            "Client '%s' is not in actor's client_scope",
            [target_client],
        ),
        "rule": "authority/main.rego:check_client_scope",
        "wsp_section": "2.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 4: Escalation for sensitive actions (agent actors)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Escalation check
# description: Sensitive actions by agent actors require human approval
# custom:
#   wsp_section: "5.1"
check_authority := result if {
    input.identity.actor_type == "agent"
    escalation_required(input.action)
    in_scope(input.action, input.identity.authority_scope)
    not in_excludes(input.action, input.identity.authority_excludes)
    result := {
        "decision": "ESCALATE",
        "reason": sprintf(
            "Action '%s' requires human approval for agent actors",
            [input.action],
        ),
        "rule": "authority/main.rego:check_escalation",
        "wsp_section": "5.1",
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 5: ALLOW — action in scope, not excluded, passes all checks
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Authority allow
# description: Action is within authority_scope and not excluded
# custom:
#   wsp_section: "2.0"
check_authority := result if {
    in_scope(input.action, input.identity.authority_scope)
    not in_excludes(input.action, input.identity.authority_excludes)
    not pod_isolation_violated
    not client_scope_violated
    not must_escalate
    result := {
        "decision": "ALLOW",
        "reason": sprintf(
            "Action '%s' is within authority_scope and not excluded",
            [input.action],
        ),
        "rule": "authority/main.rego:check_authority",
        "wsp_section": "2.0",
    }
}


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

# Check if action matches a scope/exclude pattern
# Supports exact match and wildcard: "client.*" matches "client.read"
action_matches(action, pattern) if {
    action == pattern
}

action_matches(action, pattern) if {
    endswith(pattern, ".*")
    prefix := trim_suffix(pattern, ".*")
    startswith(action, concat("", [prefix, "."]))
}

action_matches(action, pattern) if {
    pattern == "*"
}

# Check if action is in authority_scope
in_scope(action, scope) if {
    some pattern in scope
    action_matches(action, pattern)
}

# Check if action is in authority_excludes
in_excludes(action, excludes) if {
    some pattern in excludes
    action_matches(action, pattern)
}

# Actions that require escalation (human approval) for agent actors
# WSP 5.1: Mandatory Human Approval for Trade Execution
escalation_required(action) if {
    action in {"order.submit", "wire.send", "account.close"}
}

# Condition checks for the ALLOW rule
pod_isolation_violated if {
    input.identity.archetype == "tier5_hedge_fund"
    input.identity.pod_id != null
    input.context.target_pod_id != null
    input.identity.pod_id != input.context.target_pod_id
}

client_scope_violated if {
    count(input.identity.client_scope) > 0
    target_client := object.get(input.context, "client_id", input.target_id)
    target_client != null
    not target_client in input.identity.client_scope
}

must_escalate if {
    input.identity.actor_type == "agent"
    escalation_required(input.action)
}

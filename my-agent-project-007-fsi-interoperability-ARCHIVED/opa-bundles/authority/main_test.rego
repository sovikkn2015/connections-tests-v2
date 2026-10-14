# authority/main_test.rego — OPA native tests for M2 authority rules (BLOCKER 3)
#
# Tests all 5 authority rules + default deny:
#   1. Default deny when action not in scope
#   2. Explicit excludes always deny
#   3. Pod isolation denies cross-pod access (Tier 5 HF)
#   4. Client scope denies out-of-scope client access
#   5. Escalation for sensitive agent actions
#   6. Allow when action in scope and no violations
#
# Every rule includes wsp_section annotation (Rule 12).

package authority.main_test

import rego.v1

import data.authority.main


# ═══════════════════════════════════════════════════════════════════
# TEST: Default deny — action not in authority_scope
# ═══════════════════════════════════════════════════════════════════

test_default_deny_action_not_in_scope if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["client.read", "portfolio.read"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "order.submit",
        "target_id": null,
        "context": {},
    }
    result.decision == "DENY"
    result.wsp_section == "1.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Explicit excludes — always deny first
# ═══════════════════════════════════════════════════════════════════

test_excludes_deny_exact_match if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["client.read", "order.submit"],
            "authority_excludes": ["order.submit"],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "order.submit",
        "target_id": null,
        "context": {},
    }
    result.decision == "DENY"
    contains(result.reason, "excluded")
    result.wsp_section == "2.0"
}

test_excludes_deny_wildcard if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier3_broker_dealer",
            "role": "advisor",
            "authority_scope": ["client.*", "order.*"],
            "authority_excludes": ["order.*"],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "order.draft",
        "target_id": null,
        "context": {},
    }
    result.decision == "DENY"
    contains(result.reason, "excluded")
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Pod isolation — Tier 5 HF cross-pod denied
# ═══════════════════════════════════════════════════════════════════

test_pod_isolation_denies_cross_pod if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier5_hedge_fund",
            "role": "portfolio_manager",
            "authority_scope": ["portfolio.read", "positions.read"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": "pod-alpha",
        },
        "action": "portfolio.read",
        "target_id": null,
        "context": {"target_pod_id": "pod-beta"},
    }
    result.decision == "DENY"
    contains(result.reason, "Pod isolation")
    result.wsp_section == "2.0"
}

test_pod_isolation_allows_same_pod if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier5_hedge_fund",
            "role": "portfolio_manager",
            "authority_scope": ["portfolio.read"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": "pod-alpha",
        },
        "action": "portfolio.read",
        "target_id": null,
        "context": {"target_pod_id": "pod-alpha"},
    }
    result.decision == "ALLOW"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Client scope — deny access to out-of-scope client
# ═══════════════════════════════════════════════════════════════════

test_client_scope_denies_out_of_scope if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["client.read"],
            "authority_excludes": [],
            "client_scope": ["C-111", "C-222"],
            "pod_id": null,
        },
        "action": "client.read",
        "target_id": "C-999",
        "context": {},
    }
    result.decision == "DENY"
    contains(result.reason, "client_scope")
    result.wsp_section == "2.0"
}

test_client_scope_allows_in_scope if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["client.read"],
            "authority_excludes": [],
            "client_scope": ["C-111", "C-222"],
            "pod_id": null,
        },
        "action": "client.read",
        "target_id": "C-111",
        "context": {},
    }
    result.decision == "ALLOW"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Escalation — agent actors on sensitive actions
# ═══════════════════════════════════════════════════════════════════

test_escalation_agent_order_submit if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "agent",
            "archetype": "tier4_independent_ria",
            "role": "agent_execution",
            "authority_scope": ["order.submit", "order.draft"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "order.submit",
        "target_id": null,
        "context": {},
    }
    result.decision == "ESCALATE"
    contains(result.reason, "human approval")
    result.wsp_section == "5.1"
}

test_escalation_not_triggered_for_human if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["order.submit"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "order.submit",
        "target_id": null,
        "context": {},
    }
    result.decision == "ALLOW"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Allow — action in scope, no violations
# ═══════════════════════════════════════════════════════════════════

test_allow_simple_read if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier4_independent_ria",
            "role": "advisor",
            "authority_scope": ["client.read", "portfolio.read"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "client.read",
        "target_id": null,
        "context": {},
    }
    result.decision == "ALLOW"
    result.wsp_section == "2.0"
}

test_allow_wildcard_scope if {
    result := main.check_authority with input as {
        "identity": {
            "actor_type": "human",
            "archetype": "tier3_broker_dealer",
            "role": "advisor",
            "authority_scope": ["client.*"],
            "authority_excludes": [],
            "client_scope": [],
            "pod_id": null,
        },
        "action": "client.update",
        "target_id": null,
        "context": {},
    }
    result.decision == "ALLOW"
}

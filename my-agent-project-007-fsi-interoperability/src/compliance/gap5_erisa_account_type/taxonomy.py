"""
Gap 5 — Account-type taxonomy sets.

See .kiro/specs/gap5-erisa-account-type.md R1.2, R1.3, R1.4.
"""

from __future__ import annotations

from compliance.gap5_erisa_account_type._types import AccountType

# R1.2 — Retirement set (9 members).
RETIREMENT_SET: frozenset[AccountType] = frozenset(
    {
        AccountType.traditional_ira,
        AccountType.roth_ira,
        AccountType.sep_ira,
        AccountType.simple_ira,
        AccountType.k401,
        AccountType.k403b,
        AccountType.k457,
        AccountType.erisa_pension,
        AccountType.erisa_profit_sharing,
    }
)

# R1.3 — ERISA-governed set (5 members). Narrower than RETIREMENT_SET;
# IRAs are IRC-governed with fiduciary overlay but are NOT ERISA.
ERISA_GOVERNED_SET: frozenset[AccountType] = frozenset(
    {
        AccountType.k401,
        AccountType.k403b,
        AccountType.k457,
        AccountType.erisa_pension,
        AccountType.erisa_profit_sharing,
    }
)

# R1.4 — Documentation helper. Used by Gap 1 / M12; NOT a gating input.
TAX_DEFERRED_SET: frozenset[AccountType] = frozenset(
    {
        AccountType.traditional_ira,
        AccountType.sep_ira,
        AccountType.simple_ira,
        AccountType.k401,
        AccountType.k403b,
        AccountType.k457,
        AccountType.erisa_pension,
        AccountType.erisa_profit_sharing,
        AccountType.account_529,
        AccountType.hsa,
    }
)


def is_retirement(account_type: AccountType) -> bool:
    return account_type in RETIREMENT_SET


def is_erisa_governed(account_type: AccountType) -> bool:
    return account_type in ERISA_GOVERNED_SET


def is_tax_deferred(account_type: AccountType) -> bool:
    return account_type in TAX_DEFERRED_SET


# Consistency invariants — asserted at import time so violations are
# caught by any import, including during pytest collection.
assert ERISA_GOVERNED_SET.issubset(RETIREMENT_SET), (
    "ERISA_GOVERNED_SET must be a subset of RETIREMENT_SET"
)
assert len(RETIREMENT_SET) == 9, "RETIREMENT_SET must have exactly 9 members"
assert len(ERISA_GOVERNED_SET) == 5, (
    "ERISA_GOVERNED_SET must have exactly 5 members"
)

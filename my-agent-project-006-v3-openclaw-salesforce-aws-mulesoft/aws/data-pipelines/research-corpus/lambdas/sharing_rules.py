"""Principal-scoped read-time filter for research-corpus.

Two fences for MNPI and SF sharing rules:

  1. Application-level: this module produces the WHERE clause fragments
     that the retriever uses. It expresses exactly what the user can see.
  2. Database-level: RLS policies in 002_rls_policies.sql re-enforce the
     same rules. If the app forgets to set app.current_principal, RLS
     returns zero rows.

The read-time filter mirrors the Salesforce sharing rules verbatim. The
CDC handler writes rows to `principal_visibility` whenever a sharing
event arrives on the Platform Event channel.

Public entry points:
  set_principal_context(conn, principal, role)  -- call first in every txn
  principal_filter_sql(principal, role)         -- returns WHERE fragment
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Roles that bypass sharing rules entirely. Compliance sees everything,
# including MNPI. Admin sees everything and can also see visibility grants.
PRIVILEGED_ROLES = {"compliance", "admin"}


@dataclass(frozen=True)
class PrincipalContext:
    """The identity + role the retrieval is running as."""

    principal_id: str
    role: str = "user"


def set_principal_context(cursor: Any, ctx: PrincipalContext) -> None:
    """Set the per-transaction principal context. Must be called first."""
    if not ctx.principal_id:
        raise ValueError("principal_id required; fail-closed")
    cursor.execute("SET LOCAL app.current_principal = %s", (ctx.principal_id,))
    cursor.execute("SET LOCAL app.current_role = %s", (ctx.role,))


def principal_filter_sql(ctx: PrincipalContext) -> tuple[str, dict[str, Any]]:
    """Return (where_clause, params) fragment to use as a belt-and-braces filter.

    The retriever ANDs this into its SQL even though RLS enforces the same
    rules. This gives us defense in depth: RLS catches the forgetful case,
    the explicit WHERE makes the intent visible in the query plan.
    """
    if ctx.role in PRIVILEGED_ROLES:
        return ("TRUE", {})
    clause = (
        "("
        " m.owner_principal = %(principal)s"
        " OR ("
        " m.contains_mnpi = FALSE"
        " AND EXISTS ("
        " SELECT 1 FROM principal_visibility pv"
        " WHERE pv.memo_id = m.memo_id AND pv.principal = %(principal)s"
        " )"
        " )"
        ")"
    )
    return (clause, {"principal": ctx.principal_id})

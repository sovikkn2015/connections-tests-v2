"""
Execution Specialist — Trade order lifecycle state machine with mandatory HITL.

Phase 3 module per ARCH-09. Manages order lifecycle from DRAFT through SETTLED.
HITL mandatory at PENDING_APPROVAL stage — cannot submit without human approval.
Approval tokens are SHA-256(order_id + approver_id + timestamp).
24-hour timeout on PENDING_APPROVAL → auto-cancel.
T+1 settlement: settlement_date_expected = trade_date + 1 business day.

No cross-module imports. M2/M4 compliance checks via REST (Rule 9).
All compliance decisions deterministic — no LLM (Rule 14).
"""

"""
Onboarding Specialist — Multi-session KYC workflow engine.

Phase 3 module per ARCH-09. Manages client onboarding from INITIATED through APPROVED.
HITL mandatory at COMPLIANCE_REVIEW stage.
Sanctions screening is deterministic (not LLM).
KYC feeds initial CDD record for BSA/AML (Gap 4).
Multi-session: sessions persist across days.
30-day abandonment timeout.

No cross-module imports. M2/M4 compliance checks via REST (Rule 9).
All compliance decisions deterministic — no LLM (Rule 14).
"""

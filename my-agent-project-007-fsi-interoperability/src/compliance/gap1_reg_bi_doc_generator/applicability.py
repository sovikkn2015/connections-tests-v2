"""
Gap 1 — Applicability gate.

Pure, deterministic evaluation of the Reg BI applicability precedence
ladder (R2.3). Runs before any obligation populator.

See .kiro/specs/gap1-reg-bi-doc-generator.md R2.
"""

from __future__ import annotations

from m5_config_loader import RegistrationType

from compliance.gap1_reg_bi_doc_generator._types import ApplicabilityResult
from compliance.gap1_reg_bi_doc_generator.document import GenerationInput

_INSTITUTIONAL_CLIENT_TYPES: frozenset[str] = frozenset({"entity", "trust"})


def evaluate_applicability(inp: GenerationInput) -> ApplicabilityResult:
    """Precedence ladder — first match wins (spec R2.3).

    1. auto_generate == False        -> SKIP_AUTO_DISABLED
    2. registration_type == ria_only -> SKIP_RIA
    3. client_type in {entity,trust} -> SKIP_INSTITUTIONAL
    4. else                          -> APPLICABLE

    Deterministic. No I/O. No clock.
    """
    if inp.config.auto_generate is False:
        return ApplicabilityResult.SKIP_AUTO_DISABLED

    if inp.advisor.registration_type == RegistrationType.ria_only:
        return ApplicabilityResult.SKIP_RIA

    if inp.client.client_type in _INSTITUTIONAL_CLIENT_TYPES:
        return ApplicabilityResult.SKIP_INSTITUTIONAL

    return ApplicabilityResult.APPLICABLE

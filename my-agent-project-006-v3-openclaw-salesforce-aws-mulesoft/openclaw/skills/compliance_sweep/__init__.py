"""Fanout compliance sweep skill — Narrative 3 risk alert pipeline.

Originates system-side. Takes a price-shock event (ticker + % change),
fans out to all households with that ticker position, evaluates
concentration thresholds, and writes Client_Inquiry__c rows with
type='alert' for affected clients.
"""

from .actions import (
    ComplianceSweepInput,
    ComplianceSweepOutput,
    HouseholdError,
    run,
)

__all__ = [
    "ComplianceSweepInput",
    "ComplianceSweepOutput",
    "HouseholdError",
    "run",
]

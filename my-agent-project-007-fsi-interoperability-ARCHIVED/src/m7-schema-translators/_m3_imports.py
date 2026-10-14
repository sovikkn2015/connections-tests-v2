"""
M7 Schema Translators — M3 Canonical Type Imports

Centralised import helper that loads M3 canonical types from the sibling
m3-schema-registry package.  Python's built-in ``types`` module would shadow
a bare ``from types import …``, so we use importlib to load by file path.

Every M7 translator imports canonical types through this module:

    from m7_schema_translators._m3_imports import Client, Holding, …

Rule 16: M7 imports only from M3 (canonical types).  No other cross-module
imports.
"""

import importlib.util
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_M3_TYPES_PATH = os.path.normpath(
    os.path.join(_THIS_DIR, "..", "m3-schema-registry", "types.py")
)

_spec = importlib.util.spec_from_file_location("m3_canonical_types", _M3_TYPES_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load M3 canonical types from {_M3_TYPES_PATH}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["m3_canonical_types"] = _mod
_spec.loader.exec_module(_mod)

# Re-export every symbol that M7 translators need.
# Shared enums
AccountType = _mod.AccountType
SourceSystem = _mod.SourceSystem
CostBasisMethod = _mod.CostBasisMethod
TransactionType = _mod.TransactionType
GoalType = _mod.GoalType
GoalStatus = _mod.GoalStatus
PerformanceMethodology = _mod.PerformanceMethodology
PerformancePeriod = _mod.PerformancePeriod

# Shared sub-models
SecurityIdentifier = _mod.SecurityIdentifier
Reconciliation = _mod.Reconciliation

# 1. Client
Client = _mod.Client
ClientVendorMappings = _mod.ClientVendorMappings
ClientVendorSalesforceFSC = _mod.ClientVendorSalesforceFSC
ClientVendorOrion = _mod.ClientVendorOrion
ClientVendorSchwab = _mod.ClientVendorSchwab
ClientVendorFidelity = _mod.ClientVendorFidelity

# 2. Holding
Holding = _mod.Holding

# 3. TaxLot
TaxLot = _mod.TaxLot

# 4. Transaction
Transaction = _mod.Transaction
CostBasisImpact = _mod.CostBasisImpact

# 5. Balance
Balance = _mod.Balance

# 6. Household
Household = _mod.Household
HouseholdMember = _mod.HouseholdMember
HouseholdAccount = _mod.HouseholdAccount
HouseholdVendorMappings = _mod.HouseholdVendorMappings
HouseholdVendorSFSC = _mod.HouseholdVendorSFSC
HouseholdVendorOrion = _mod.HouseholdVendorOrion
HouseholdVendorSchwab = _mod.HouseholdVendorSchwab

# 7. Performance
Performance = _mod.Performance

# 8. PlanSummary
PlanSummary = _mod.PlanSummary
PlanAssumptions = _mod.PlanAssumptions
PlanVendorMappings = _mod.PlanVendorMappings
PlanVendorEMoney = _mod.PlanVendorEMoney

# 9. Goal
Goal = _mod.Goal
GoalAssumptions = _mod.GoalAssumptions
GoalVendorMappings = _mod.GoalVendorMappings
GoalVendorSFSC = _mod.GoalVendorSFSC
GoalVendorEMoney = _mod.GoalVendorEMoney

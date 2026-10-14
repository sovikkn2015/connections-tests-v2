# Schema Decision Log

Every semantic decision about canonical types is recorded here.

| Date | Type | Field | Decision | Rationale | Decided By |
|------|------|-------|----------|-----------|-----------|
| 2026-04-14 | Household | model | Container (not unified) | SF FSC, Orion, Schwab use different grouping concepts. Unifying loses vendor semantics. | Architect |
| 2026-04-14 | TaxLot | cost_basis_method | REQUIRED enum | Different custodians default differently. Wrong method = wrong tax reporting = regulatory violation. | Architect (needs SME validation) |
| 2026-04-14 | Holding | market_value | TBD — needs SME | Does MarketValue include accrued interest? Differs by custodian feed. | PENDING SME |
| 2026-04-14 | All types | security_identifier | TBD — needs SME | Canonical ID: CUSIP? FIGI? ISIN? All three? Cross-reference service needed. | PENDING SME |
| 2026-04-15 | All 18 types | $id format | `https://007.fsi/schemas/canonical/{type}/v0.1.0` | Consistent namespace. Semver in URI. All schemas normalized to this pattern. | Architect |
| 2026-04-15 | Client | vendor_mappings | Added SF FSC, Orion, Schwab, Fidelity mappings | Same container pattern as Household. Preserves vendor-specific client IDs for reconciliation. | Architect |
| 2026-04-15 | Client | kyc_status | Added KYC verification fields | Onboarding Specialist needs KYC status for BSA/AML CDD. Feeds M2 compliance checks. | Architect |
| 2026-04-15 | Client | x-pii markers | email, phone, date_of_birth, ssn_last_four, tax_id | M4 MNPI filter uses x-pii annotation to strip fields by role/archetype. | Architect |
| 2026-04-15 | Transaction | transaction_type | Expanded to 19 types | Custodian feeds have different type codes. M7 translator normalizes. Added margin_interest, return_of_capital, corporate_action. | Architect |
| 2026-04-15 | Transaction | settlement_status | Added pending/settled/failed enum | ARCH-05 settlement states. T+1 since May 2024. | Architect |
| 2026-04-15 | Transaction | cost_basis_impact | Added realized_gain_loss, wash_sale | Tax impact tracking per transaction. Links to TaxLot. | Architect |
| 2026-04-15 | Balance | account_type | 16 account types (ERISA + tax-advantaged) | ARCH-06 Gap 5 ERISA account-type rules. OPA needs account_type for per-type compliance. | Architect |
| 2026-04-15 | Balance | is_real_time | Boolean flag | Distinguishes real-time API balance from daily SFTP file. Compliance must know data freshness. | Architect |
| 2026-04-15 | Performance | methodology | modified_dietz / daily_valuation / irr_only | Orion uses daily valuation, some custodians use modified Dietz. Must be explicit for GIPS compliance. | Architect (needs SME validation) |
| 2026-04-15 | Performance | risk metrics | sharpe_ratio, standard_deviation, max_drawdown | Required for suitability analysis. M2 OPA checks risk metrics against client risk_tolerance. | Architect |
| 2026-04-15 | SecurityProfile | is_restricted, mnpi_flag | Boolean flags | M2 restricted list check and M4 MNPI filter need these flags on the security itself. | Architect |
| 2026-04-15 | Quote | is_delayed | REQUIRED boolean | Compliance must disclose delayed quotes to clients. Alpha Vantage = delayed, Bloomberg = real-time. | Architect |
| 2026-04-15 | PlanSummary | vendor_mappings | eMoney, MoneyGuidePro, RightCapital | Same container pattern. Preserves vendor plan IDs. | Architect |
| 2026-04-15 | PlanSummary | MNPI note | Raw plan data NEVER to LLM | M4 filters to summary-level only. Full plan data stays in planning system. | Architect |
| 2026-04-15 | Goal | vendor_mappings | SF FSC FinancialGoal, eMoney, MoneyGuidePro | Goal type picklists differ across vendors. M7 normalizes to canonical enum. | Architect |
| 2026-04-15 | Goal | status | on_track/at_risk/behind/achieved/abandoned | Agent needs goal status for meeting prep and client service. | Architect |
| 2026-04-15 | InteractionSummary | crm_write_back | SF FSC, Wealthbox, Redtail | Client Service Specialist writes meeting notes back to CRM. Status tracking per vendor. | Architect |
| 2026-04-15 | InteractionSummary | compliance_review | Principal review for BD (FINRA 2210) | BD communications require principal review before delivery. RIA = not required. | Architect |
| 2026-04-15 | ComplianceAlert | wsp_section | REQUIRED field | Steering rule 19: every OPA rule must include wsp_section annotation. Alert inherits from rule. | Architect |
| 2026-04-15 | ComplianceAlert | alert_type | 15 types covering all compliance sub-modules | Maps to ARCH-06 Gaps 1-7. BSA/AML CTR/SAR always severity=critical. | Architect |
| 2026-04-15 | ComplianceAlert | sla_deadline | Deadline for acknowledgment | BSA/AML SAR = 30 days. Principal review = 4 hours. Configurable per alert_type. | Architect |
| 2026-04-15 | PaymentInstruction | iso20022_mapping | pain.001 fields (Phase 5) | ISO 20022 migration completed Nov 2025. 007 maps to pain.001 for Tier 1 bank integration. | Architect |
| 2026-04-15 | PaymentInstruction | bsa_aml | CTR/SAR/sanctions/OFAC fields | Payments >= $10K trigger CTR. Structuring patterns trigger SAR. All payments OFAC-screened. | Architect |
| 2026-04-15 | AuditEntry | provenance_chain | Per-stage SHA-256 hash chain | ARCH-06 Gap 2 liability provenance. Each module in the call chain adds its hash. | Architect |
| 2026-04-15 | AuditEntry | retention_years | Default 6 (SEC 17a-4) | Jurisdiction may require more. WORM storage enforces minimum. | Architect |
| 2026-04-15 | Balance, Order, Holding, Transaction | account_type | Unified to Balance/Order convention: taxable, traditional_ira, roth_ira, 401k, 403b, 457, sep_ira, simple_ira, trust_revocable, trust_irrevocable, custodial_utma, custodial_ugma, erisa_pension, erisa_profit_sharing, 529, hsa | BLOCKER-8 resolution. Balance.json and Order.json already used this enum (matches M5 config). Rule 10 specified a different naming convention (individual, joint_tos, ira_traditional, etc.) but 2 schemas + M5 config already committed to the Balance/Order convention. Changing would break existing M5 integration. Added account_type to Holding and Transaction schemas (were missing). MINOR version bump: new optional field on Holding and Transaction. | Schema Specialist |
| 2026-04-15 | All 18 types | Pydantic v2 models | Created in src/m3-schema-registry/types.py | BLOCKER-1 resolution. M7 translators import Pydantic models from M3 — models must exist before M7 can be built. 78 classes covering all 18 canonical types + enums + sub-models. | Schema Specialist |

| 2026-04-16 | All types | reconciliation | reconciliation=None is correct for single-source translations | Reconciliation object is populated by the reconciliation service when merging multi-vendor data for the same entity, NOT by individual M7 translators. Single-source translations correctly set reconciliation=None. | Schema Specialist |
| 2026-04-16 | TaxLot | cost_basis_method | Fidelity defaults differ by asset class | Fidelity uses average_cost for mutual funds and specific_lot for equities/ETFs. M7 Fidelity translator implements _fidelity_default_cost_basis() to select correct default by asset type. Rule 7 enforced — NEVER null. | Schema Specialist |
| 2026-04-16 | Client | vendor_mappings.fidelity | Added Fidelity translator with ClientVendorFidelity mapping | New M7 translator for Fidelity Institutional. Dual source: "fidelity" (API) / "fidelity_sftp" (daily files). Covers Client, Holding, TaxLot, Balance, Transaction. | Schema Specialist |
| 2026-04-16 | All M7 translators | datetime.utcnow() | Replaced with datetime.now(timezone.utc) | datetime.utcnow() deprecated in Python 3.12+. All M7 translators updated to use timezone-aware utcnow() helper from base.py. | Schema Specialist |
| 2026-04-16 | All M7 translators | helper functions | Deduplicated to base.py | Shared helpers (_parse_uuid, _parse_date, _parse_datetime, _safe_float, _map_time_horizon) moved from 4 translator files to base.py as module-level functions. All translators import from base. | Schema Specialist |
| 2026-04-16 | All 18 schemas | CI validation | Created scripts/validate-schemas.py | Validates JSON parse, Draft 2020-12 dialect, $id format, and description presence on all properties. Exit code 0/1 for CI integration. | Schema Specialist |

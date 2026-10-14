# Gap 7 — Cross-Border — Decision Log

## D1. Matrix is data, logic is thin

The 5×5 jurisdiction matrix is a single dict literal. Every cell is
explicit. Any future adequacy-decision change (e.g., EU approves HK)
is a one-line data edit — no code changes, no re-review needed beyond
the matrix diff.

## D2. Fail-closed is structural, not optional

`matrix_lookup` raises `UndefinedJurisdictionPair`. The egress gate
catches it and emits DENY with rule_id `gap7.matrix.undefined_pair`.
Both paths are unit-tested. The only way to add a new jurisdiction is
to extend the matrix — which in turn triggers the import-time
cardinality assertion. Drift is impossible.

## D3. MNPI-by-jurisdiction sits AFTER GDPR / MiFID / MAS / HKMA

The egress pipeline evaluates regulatory regimes first, then MNPI.
Rationale: if the egress would fail MiFID II, we never got to the
MNPI scan; the stronger DENY short-circuits. When we do reach the
MNPI scan, we know the regulatory side is green.

## D4. MiFID II is opt-in

MiFID II only runs when `client_classification` is supplied. US-only
flows skip cleanly (no accidental EU classification on a US-only
request). This also keeps the gate fast for 95% of traffic.

## D5. Rationale charset allows `,:` for field lists

Gap 5's rationale regex was `[A-Za-z0-9 _\-\.\(\)/§]`. Gap 7 extends
it with `,:` because cross-border MNPI rationales list field names
(`"EU PII fields: national_id,tax_id_eu"`). The expanded charset is
still PII-safe.

## D6. No cross-gap imports

Gap 7 does NOT import from Gap 5, Gap 6, or any other Gap. It imports
only from `m5_config_loader` (shared data contract) and stdlib /
pydantic. Steering rule 9 preserved.

## D7. The egress gate is M6's hook point

Gap 7 lives in `src/compliance/gap7_cross_border/` and exports
`EgressGate`. M6 wires it into the vendor-call code path. Gap 7 does
NOT import M6 code — the integration direction is strictly M6 → Gap 7.

# Bloomberg BLPAPI Test Fixtures

Deterministic JSON captures used by :class:`FakeBlpapiClient` for record-and-replay
integration tests.

**Derivation**: these fixtures are **synthesized** from the published
BLPAPI Core Developer Guide response schemas, NOT captured from a licensed Bloomberg
Terminal session. Bloomberg's data-distribution license forbids redistributing real
captures. The shapes match the documented response Elements exactly so the unit
tests and the real BLPAPI session see identical payload keys.

**Fixture naming convention**:

    {operation}_{scenario}.json

Where:
- `operation` ∈ {`reference_data`, `historical_data`, `intraday_tick`, `corporate_actions`}
- `scenario` is a short slug describing what the fixture represents
  (`aapl_basic`, `us10yr_5y`, `msft_splits`, etc.).

**Schema** — each file contains:

```json
{
  "data":   { ... operation-specific JSON-serialised response ... },
  "partial": false,
  "vendor_response_code": 0
}
```

Errors are injected programmatically via `FakeBlpapiClient.set_error()` — no
fixture file needed.

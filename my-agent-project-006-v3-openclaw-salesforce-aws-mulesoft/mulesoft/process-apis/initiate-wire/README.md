# initiate-wire Process API — V3

Mule 4.9.x Maven project. One write endpoint + health:

- `POST /api/wires` — initiate a wire transfer
- `GET  /api/health` — liveness probe

The write path forwards to Dwolla sandbox at `api-sandbox.dwolla.com` after an OFAC SDN screen of the beneficiary bank name.

## Flow summary

```
POST /api/wires
  -> 403 if plan_hash | approval_token_hash missing
  -> 403 if amount_usd > $100K and dual_approval_token_hash missing  (steering rule 5)
  -> 400 on other shape failures
  -> GET OFAC SDN feed (public Treasury XML)
  -> 451 on beneficiary match
  -> POST Dwolla /token (client_credentials OAuth)
  -> POST Dwolla /transfers
  -> 200 canonical { wire_id: "DWOLLA-...", status: "initiated", ... }
  -> 502 on Dwolla 4xx/5xx; 504 on timeout
```

## V3 contract

| Field | Required | Notes |
|---|---|---|
| `amount_usd` | yes | > 0 |
| `currency` | no | USD/EUR/GBP/JPY; default USD |
| `beneficiary_bank` | yes | screened against OFAC SDN |
| `beneficiary_account` | yes | |
| `source_account_id` | yes | |
| `plan_hash` | yes | SHA-256 hex |
| `approval_token_hash` | yes | SHA-256 hex |
| `dual_approval_token_hash` | conditional | required when `amount_usd > 100,000` |
| `reference_memo` | no | |

## Build, test, deploy

```bash
# 6 MUnit tests, hermetic
mvn test

# local dev, canned response
mvn mule:run -Dmock_mode=true

# deploy to CloudHub 2.0
export ANYPOINT_CONNECTED_APP_ID="<from Anypoint Access Mgmt, Connected Apps>"
export ANYPOINT_CONNECTED_APP_SECRET="<from the same screen>"
export ANYPOINT_ORG_ID="<business-group id>"
mvn clean deploy -Pcloudhub-sandbox -DskipTests
```

Secure properties at Runtime Manager -> Settings -> Properties -> Show secure properties:

| Property name | Source |
|---|---|
| `dwolla.client_id` | `/006-v3/vendors/dwolla` -> `client_id` |
| `dwolla.client_secret` | `/006-v3/vendors/dwolla` -> `client_secret` |

## Deliberate non-goals

- **Fuzzy OFAC matching.** This is exact-match on canonical names. A real Treasury-grade screener handles AKAs, weak matches, transliteration. V3 keeps it deterministic so the gate is demonstrable in a demo.
- **SWIFT / Fedwire.** V3 uses Dwolla sandbox because it is the cleanest vendor to exercise a full OAuth + transfer-create happy path in a reproducible deploy. Live SWIFT/Fedwire is out of scope.
- **No LLM, no audit write, no raw-token logging.** Same non-goals as submit-order. Audit is written by the upstream Lambda.

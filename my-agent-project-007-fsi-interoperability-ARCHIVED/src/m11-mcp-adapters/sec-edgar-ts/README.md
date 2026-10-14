# SEC EDGAR MCP Adapter — TypeScript Reference Implementation

TypeScript implementation of the SEC EDGAR M11 adapter, proving Rule 10 polyglot
compliance. Implements the **identical MCP interface** as the Python `sec-edgar/`
adapter — M6 gateway sees no difference between the two.

## Purpose

This adapter resolves the Rule 10 polyglot violation identified in ADR-001.
It serves as the **template for all future TypeScript M11 adapters**.

## MCP Interface Contract

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Server info + health check |
| `/tools/list` | POST | Capability discovery (3 tools) |
| `/tools/call` | POST | Tool execution |

## Tools

| Tool | Description |
|---|---|
| `search_filings` | Search SEC EDGAR by ticker/name, filing type, date range |
| `get_filing` | Retrieve filing metadata by accession number |
| `get_company_facts` | Get XBRL company facts by CIK number |

## Run

```bash
# Development
npm install
npm start

# Docker
docker build -t sec-edgar-ts .
docker run -p 8070:8070 -e SEC_EDGAR_USER_AGENT="YourApp you@example.com" sec-edgar-ts

# Tests
npm test
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8070` | Server port |
| `SEC_EDGAR_USER_AGENT` | `007-FSI-Platform admin@example.com` | Required by SEC |
| `SEC_EDGAR_RATE_LIMIT_RPM` | `600` | Requests per minute |
| `SEC_EDGAR_RATE_LIMIT_BURST` | `10` | Burst capacity |

## Architecture

- **Rule 10**: M11 is polyglot — TypeScript for REST, Python for BLPAPI/gRPC/SFTP
- **Rule 1**: Implements GET / + POST /tools/list + POST /tools/call
- **Rule 4**: Token-bucket rate limiter (10 req/s SEC limit)
- **Rule 20**: Zero credentials in code — all config via env vars
- **ADR-003**: TypeScript reference implementation for Phase 4

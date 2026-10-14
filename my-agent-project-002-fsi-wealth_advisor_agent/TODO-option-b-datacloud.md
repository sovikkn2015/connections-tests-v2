# TODO: Option B — Data Cloud Version

Data Cloud is now provisioned and live in the org.

## What to do
- Create folder: `my-agent-project-003-fsi-wealth_advisor_agent-datacloud`
- Same agent architecture as Option A but data lives in Data Cloud instead of CRM objects
- Create Data Cloud data streams for: Household, Client, Financial Account, Financial Goal, Meeting
- Map schemas and configure identity resolution
- Apex actions query Data Cloud via SOQL on Data Cloud objects instead of custom objects
- Agent script and topics remain identical

## Org Details
- Home Org ID: 00DgL00000O4JFx
- Data Cloud Instance: CDP2-AWS-PROD8-CACENTRAL1
- Tenant Endpoint: m04tayr2m0ydkmrygm4dq2rvgk.c360a.salesforce.com
- Data Spaces: 1
- Connections: 1

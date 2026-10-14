# Wave 2 — SAM Deployment (Project 006 V3)

**Final status: BLOCKED**

Stack `openclaw-mcp-006-v3` did not create. All resources rolled back and were deleted. Nothing is live in AWS account 875460787302 / us-east-1 from this wave.

| Handoff value | Result |
|---|---|
| `ApiUrl` | **NOT AVAILABLE — stack rolled back** |
| `NatEip` | **NOT AVAILABLE — stack rolled back** |
| `McpBaseLayerArn` | not available (layer was created, then `DELETE_SKIPPED` during rollback but stack is gone) |
| `VpcId` | not available |

**Blocker:** AWS service quota `vpc:L-FE5A380F` (“NAT gateways per Availability Zone”) is exhausted in us-east-1. Current limit is **5** (adjustable). Five existing NAT gateways are already present in the account under unrelated `whalthy-v17 / v20 / v24 / v26 / v27` VPCs, and the CloudFormation attempt to create `McpNatGateway` failed with `ServiceLimitExceeded`, which cancelled every other in-flight resource and triggered rollback.

**Wave 4 (Mulesoft) cannot start** — it needs `ApiUrl` and `NatEip` from this wave.

---

## Step 0 — prereq checks

```
$ which sam && sam --version
/Library/Frameworks/Python.framework/Versions/3.10/bin/sam
SAM CLI, version 1.158.0

$ docker info | head -3
Client:
 Namespace:     finch
 Debug Mode:    false
# (docker backed by Finch v2.2.1 on Amazon Linux 2023 aarch64 VM — docker API reachable)

$ aws sts get-caller-identity --region us-east-1 --query 'Account' --output text
875460787302
```

All prereqs passed.

---

## Step 1 — `sam build`

Ran from `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/aws/`.

```
$ sam build --template sam-template.yaml
Building codeuri: .../aws/mcp-servers/market-data      functions: MarketDataFunction
Building codeuri: .../aws/mcp-servers/sec-edgar        functions: SecEdgarFunction
Building codeuri: .../aws/mcp-servers/news-search      functions: NewsSearchFunction
Building codeuri: .../aws/mcp-servers/salesforce-crm   functions: SalesforceCrmFunction
Building codeuri: .../aws/mcp-servers/sf-auth-proxy    functions: SfAuthProxyFunction
Building codeuri: .../aws/mcp-servers/mulesoft-actions functions: MulesoftActionsFunction
Building codeuri: .../aws/mcp-servers/bff              functions: BffFunction

Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

All 7 Lambdas + the `McpBaseLayer` layer built cleanly under `python3.12 / arm64`. No warnings from pip resolvers.

---

## Step 2 — `sam deploy`

Command issued verbatim per runbook:

```
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name openclaw-mcp-006-v3 \
  --region us-east-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --resolve-s3 \
  --parameter-overrides \
      EnvName=v3 \
      BedrockRegion=us-east-1 \
      SonnetModelId=us.anthropic.claude-sonnet-4-6 \
      MulesoftModeParam=mock \
      CorsAllowOrigin=http://localhost:5173
```

### CloudFormation change-set summary (create action)

Change set accepted without review (`--no-confirm-changeset`). Resources CloudFormation attempted to create:

- `McpBaseLayer` (Lambda LayerVersion) ✅ CREATE_COMPLETE
- 7 × `AWS::Logs::LogGroup` (one per function) ✅ CREATE_COMPLETE
- 7 × `AWS::IAM::Role` (function execution roles) ✅ CREATE_COMPLETE
- VPC + IGW + IGW attach + 2 subnets + 2 route tables + SG ✅ CREATE_COMPLETE (some still in-flight at cancel time)
- `McpNatEip` (EIP), `McpNatGateway` (NAT Gateway) ❌ **FAILED**
- 7 × `AWS::Lambda::Function` — cancelled when NAT failed
- `AWS::ApiGateway::RestApi` / `Deployment` / `Stage` / routes — never reached

### Failing event (raw, from deploy stream)

```
CREATE_FAILED   AWS::EC2::NatGateway   McpNatGateway
Resource handler returned message:
"Performing this operation would exceed the limit of 5 NAT gateways
(Service: Ec2, Status Code: 400,
 Request ID: c369a7b8-60fe-4ecf-aa7f-ea7e3efa0e3b)
 (SDK Attempt Count: 1)"
(RequestToken: 38064fe2-bb76-9310-7816-e5af75dd1fdc,
 HandlerErrorCode: ServiceLimitExceeded)
```

Cascading cancellation after the NAT failure (from the deploy stream):

```
CREATE_FAILED  AWS::Lambda::Function      SalesforceCrmFunction    Resource creation cancelled
CREATE_FAILED  AWS::EC2::RouteTable       McpPublicRt              Resource creation cancelled
CREATE_FAILED  AWS::EC2::EIP              McpNatEip                Resource creation cancelled
CREATE_FAILED  AWS::Lambda::Function      SecEdgarFunction         Resource creation cancelled
CREATE_FAILED  AWS::EC2::RouteTable       McpPrivateRt             Resource creation cancelled
CREATE_FAILED  AWS::Lambda::Function      BffFunction              Resource creation cancelled
CREATE_FAILED  AWS::Lambda::Function      MarketDataFunction       Resource creation cancelled
CREATE_FAILED  AWS::EC2::SecurityGroup    McpLambdaSg              Resource creation cancelled
CREATE_FAILED  AWS::Lambda::Function      NewsSearchFunction       Resource creation cancelled
CREATE_FAILED  AWS::Lambda::Function      SfAuthProxyFunction      Resource creation cancelled

ROLLBACK_IN_PROGRESS  AWS::CloudFormation::Stack  openclaw-mcp-006-v3
  The following resource(s) failed to create: [McpLambdaSg, BffFunction,
  MarketDataFunction, SecEdgarFunction, NewsSearchFunction, SfAuthProxyFunction,
  McpPublicRt, SalesforceCrmFunction, McpNatGateway, McpPrivateRt, McpNatEip].
  Rollback requested by user.
```

### Final status

```
$ aws cloudformation describe-stacks --stack-name openclaw-mcp-006-v3 \
    --region us-east-1 \
    --query 'Stacks[0].[StackName,StackStatus,StackStatusReason]' --output json
[
    "openclaw-mcp-006-v3",
    "ROLLBACK_COMPLETE",
    null
]
```

`sam deploy` final line:

```
Error: Failed to create/update the stack: openclaw-mcp-006-v3,
Waiter StackCreateComplete failed: Waiter encountered a terminal failure state:
For expression "Stacks[].StackStatus" we matched expected path:
"ROLLBACK_COMPLETE" at least once
```

### `describe-stack-events` dump (per runbook Step 2)

By the time describe-stack-events ran, the `CREATE_FAILED` entries had rolled off the `--max-items 10` window because rollback generated a large burst of DELETE events. The CREATE_FAILED events are preserved verbatim above from the `sam deploy` stream.

```
$ aws cloudformation describe-stack-events --stack-name openclaw-mcp-006-v3 \
    --region us-east-1 --max-items 10 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`]' \
    --output json
[]
```

### Root cause — NAT gateway quota

```
$ aws ec2 describe-nat-gateways --region us-east-1 \
    --filter "Name=state,Values=pending,available" \
    --query 'NatGateways[].[NatGatewayId,VpcId,State,Tags[?Key==`Name`].Value|[0]]' \
    --output table
+-----------------------+-----------------------+------------+---------------------+
|  nat-0f91025766cc964cc|  vpc-069961aad94bc4025|  available |  whalthy-v24-nat-1  |
|  nat-021b5b9a46511dc60|  vpc-062bd3ecbbbf3930e|  available |  whalthy-v20-nat-1  |
|  nat-07f1975115e29e45e|  vpc-01747e65848ba7eb8|  available |  whalthy-v17-nat-1  |
|  nat-0fb71f7ea3bffee49|  vpc-0bb54aeba9050ad55|  available |  whalthy-v27-nat-1  |
|  nat-0195d980032526ddd|  vpc-08e0dab5f89c2edb4|  available |  whalthy-v26-nat-1  |
+-----------------------+-----------------------+------------+---------------------+

$ aws service-quotas get-service-quota --service-code vpc \
    --quota-code L-FE5A380F --region us-east-1 \
    --query 'Quota.[QuotaName,Value,Adjustable]' --output json
["NAT gateways per Availability Zone", 5.0, true]
```

Five NATs are in use across four unrelated `whalthy-v*` VPCs. Our `McpNatGateway` would have been the sixth. The quota is **adjustable** — a Service Quotas increase request (or retiring a stale whalthy NAT) is required before this stack can be created.

---

## Step 3 — capture outputs

**SKIPPED.** Stack is `ROLLBACK_COMPLETE` with no resources. `describe-stacks … Outputs` returns null. No `ApiUrl`, `NatEip`, `McpBaseLayerArn`, or `VpcId` exists.

---

## Step 4 — Lambda health smoke

**SKIPPED.** No API Gateway was created. Nothing to curl against.

---

## Step 5 — BFF tools/list for 2 MCP servers

**SKIPPED.** Dependent on Step 4.

---

## Step 6 — smoke-call `market-data` quote for AAPL

**SKIPPED.** Dependent on Step 4.

---

## Deviations from runbook

1. **Step 2 failed** — NAT gateway service quota exceeded in us-east-1. Raw error captured above. Per runbook (“No auto-recovery. Fail loud.”), deploy was not retried and the template was not modified.
2. **Step 2 `describe-stack-events` returned `[]`** — the 10-event tail was consumed by rollback DELETE events. The CREATE_FAILED events from the `sam deploy` output stream are preserved verbatim in this document.
3. **Steps 3–6 skipped** — no live stack to probe.
4. **No parameter or SSM issue encountered.** All parameters resolved (the MCP base layer built, all log groups / IAM roles / VPC / IGW / subnets created in-flight). The failure is purely an account-level quota, not a template or credential defect.

---

## Unblock — options for the operator

Not executed. Listed for the user to choose.

1. **Request quota increase** — `aws service-quotas request-service-quota-increase --service-code vpc --quota-code L-FE5A380F --desired-value 7 --region us-east-1`. Approval can take minutes to hours.
2. **Retire a stale whalthy NAT** — any of the five `whalthy-v*` NAT gateways appear unrelated to project 006. If one is known-dead, deleting it frees capacity for this stack. Destructive, requires explicit user confirmation before action.
3. **Rewire template to skip NAT** — `mulesoft-actions` Lambda only needs NAT egress for the Anypoint allowlist. In `MulesoftModeParam=mock` (which is what Wave 2 deploys), the Mulesoft Lambda never calls out to Anypoint; a temporary template variant that drops the NAT (and the private subnet / route table / EIP) would deploy today and still pass the Wave 2 smoke tests. This defers the NAT dependency to Wave 4. Requires a template change, not in scope for an autonomous deploy.

---

## Final status

**BLOCKED — AWS account service quota (VPC NAT Gateways per AZ = 5) exhausted in us-east-1. Stack `openclaw-mcp-006-v3` is `ROLLBACK_COMPLETE` and empty. Wave 4 cannot proceed until a NAT slot is freed or the template is adjusted.**

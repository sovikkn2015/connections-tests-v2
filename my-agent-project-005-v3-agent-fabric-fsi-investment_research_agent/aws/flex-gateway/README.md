# Flex Gateway — Project 005 V3 Phase 1 Deployment

Internal MuleSoft Flex Gateway running on ECS Fargate, sitting **in parallel** with the existing V2 API Gateway. Phase 3 will cut the upstream clients over to Flex and deprecate the V2 path.

## What lives where

```
aws/flex-gateway/
├── Dockerfile              # FROM mulesoft/flex-gateway:latest + mount points
├── flex-gateway-config.yaml# listener, cluster, /health, Anypoint connect-back
├── registration.sh         # pulls creds from Secrets Manager → flexctl register
├── entrypoint.sh           # runs registration.sh, execs flex-gateway
└── README.md               # you are here

aws/flex-gateway-sam.yaml   # separate CFN stack (ECR + ECS + ALB + IAM)
agent-fabric/api-instance.yaml  # ApiInstance the 5 PolicyBindings attach to
```

Nothing in `aws/sam-template.yaml` is modified — the two stacks coexist.

## Prerequisites

| Item | Where it lives |
|---|---|
| AWS account | `875460787302` (us-east-1) |
| MuleSoft credentials | AWS Secrets Manager: `/006-v2/mulesoft/credentials` |
| Anypoint org + env IDs | Anypoint Platform → Access Management → Business Groups |
| Private subnets (≥2 AZs) | Existing VPC |
| ACM certificate | Must cover the FQDN used to reach the ALB |
| IAM permission to `sam deploy` | CFN + ECS + ECR + IAM + ELB + Route53 |
| Docker daemon | For image build |

Secrets Manager entry must be a JSON blob:

```json
{
  "client_id":            "<anypoint connected-app client id>",
  "client_secret":        "<anypoint connected-app client secret>",
  "connected_app_id":     "<optional — falls back to client_id>",
  "anypoint_platform_url":"https://anypoint.mulesoft.com"
}
```

The task role created by the SAM stack has `secretsmanager:GetSecretValue` on **this one secret ARN only** — no wildcard.

## Deploy

All commands run from the project root:
`my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent/`

### 1. Build the SAM stack (ECR + ECS + ALB)

```bash
sam build -t aws/flex-gateway-sam.yaml
```

### 2. Deploy the stack

Fill in the parameter values from your environment. Nothing is hardcoded.

```bash
sam deploy -t aws/flex-gateway-sam.yaml \
  --stack-name ir-flex-gateway-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --parameter-overrides \
      Stage=prod \
      MuleSoftSecretId=/006-v2/mulesoft/credentials \
      VpcId=<vpc-xxxxxxxx> \
      PrivateSubnetIds=<subnet-aaa>,<subnet-bbb> \
      AnypointOrgId=<org-uuid> \
      AnypointEnvId=<env-uuid> \
      AlbCertificateArn=arn:aws:acm:us-east-1:<acct>:certificate/<cert-id> \
      SalesforceIngressCidrs=136.146.0.0/16,136.147.0.0/16 \
      AdditionalIngressCidrs=10.0.0.0/8 \
      FlexGatewayImageTag=latest
```

Optional — create an internal Route53 CNAME:

```bash
sam deploy -t aws/flex-gateway-sam.yaml \
  --stack-name ir-flex-gateway-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      ... (as above) \
      InternalHostedZoneId=<Z0123456ABCDEF> \
      InternalDnsName=flex-gateway.ir-internal.example.com
```

The stack outputs include `FlexGatewayUrl` (ALB DNS) and, if a zone was supplied, `FlexGatewayInternalFqdn`.

### 3. Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
      $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

### 4. Build and push the Flex Gateway image

```bash
# From aws/flex-gateway/ because Dockerfile uses local COPY paths
cd aws/flex-gateway

REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name ir-flex-gateway-prod \
  --query "Stacks[0].Outputs[?OutputKey=='FlexGatewayRepositoryUri'].OutputValue" \
  --output text)

docker build -t "${REPO_URI}:latest" .
docker push "${REPO_URI}:latest"
```

Force the service to pull the new image:

```bash
CLUSTER=$(aws cloudformation describe-stacks \
  --stack-name ir-flex-gateway-prod \
  --query "Stacks[0].Outputs[?OutputKey=='FlexGatewayClusterName'].OutputValue" --output text)

aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service ir-flex-gateway-service-prod \
  --force-new-deployment \
  --region us-east-1
```

### 5. Verify

```bash
FQDN=$(aws cloudformation describe-stacks \
  --stack-name ir-flex-gateway-prod \
  --query "Stacks[0].Outputs[?OutputKey=='FlexGatewayUrl'].OutputValue" --output text)

curl -v "${FQDN}/health"    # expect 200 OK
```

In Anypoint Platform → Runtime Manager, a new Flex Gateway named `ir-flex-gateway-prod` should show as **Running** within ~2 minutes of the first task starting.

### 6. Bind policies to the `fsi-mcp-servers` ApiInstance

After `agent-fabric/api-instance.yaml` has been applied via Anypoint CLI, the five existing policies (`mnpi-filter`, `rate-limit`, `circuit-breaker`, `finra-audit`, `auth-mtls`) attach automatically because they all reference `targetRef.kind=ApiInstance name=fsi-mcp-servers`.

## Version pinning (production)

`latest` is fine for Phase 1 bring-up but MUST be replaced before prod cutover:

1. Find the tag you want in Docker Hub (`docker pull mulesoft/flex-gateway:1.8.0` etc.)
2. Rebuild locally with `FROM mulesoft/flex-gateway:1.8.0` (or override in `Dockerfile`)
3. Tag the resulting image with the same version: `docker tag ${REPO_URI}:latest ${REPO_URI}:1.8.0`
4. Redeploy the SAM stack with `FlexGatewayImageTag=1.8.0`
5. Retain the digest: `aws ecr describe-images --repository-name ir-flex-gateway-prod --image-ids imageTag=1.8.0`

## Teardown

```bash
# Empty ECR first (SAM won't delete a non-empty repository)
aws ecr batch-delete-image \
  --repository-name ir-flex-gateway-prod \
  --image-ids "$(aws ecr list-images --repository-name ir-flex-gateway-prod --query 'imageIds[*]' --output json)"

sam delete --stack-name ir-flex-gateway-prod --region us-east-1
```

## Troubleshooting

| Symptom | First place to look |
|---|---|
| Task stuck in `PROVISIONING` | Subnet NAT / route to ECR + Secrets Manager |
| Task fails on `[registration]` | Check `MULESOFT_SECRET_ID` value + task role policy |
| Registered but not receiving traffic | ALB target group health; SG ingress from ALB to :8080 |
| Policies not applying | Anypoint → API Manager → confirm `fsi-mcp-servers` ApiInstance exists + is bound |
| `flexctl` auth errors | Secret JSON keys must be `client_id` / `client_secret` exactly |

## Phase 2 / Phase 3 pointers

- Phase 2 adds Consumer Credentials, Org App registration, and tightens the SG CIDRs.
- Phase 3 cuts upstream clients (`MCP_GATEWAY_URL` in `aws/sam-template.yaml` Strands agents) to this ALB and decommissions the V2 API Gateway `/sec-edgar/*`, `/market-data/*`, `/news-search/*` paths.

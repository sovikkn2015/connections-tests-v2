# Deployment Notes — Project 006

## Langfuse Observability

### Current: Langfuse Cloud (Dev/Demo)

The system currently uses **Langfuse Cloud** at `https://us.cloud.langfuse.com`. This is acceptable for development and demo purposes.

All components already read the Langfuse endpoint from the `LANGFUSE_BASE_URL` environment variable:

- **AgentCore container** — reads from Secrets Manager (`openclaw-fsi-secrets`)
- **MCP Lambda functions** — reads from SAM template parameters
- **OpenClaw config** — reads from environment at runtime

No code changes are needed to switch endpoints.

### Production: Self-Hosted Langfuse (FSI Requirement)

For production FSI deployments, Langfuse must be self-hosted so that all trace data stays within the VPC. Agent traces may contain client names, account references, and query context that should not leave the AWS boundary.

#### Option A: EC2 (simplest)

```bash
docker run -d \
  --name langfuse \
  -p 3000:3000 \
  -e DATABASE_URL="postgresql://user:pass@your-rds-host:5432/langfuse" \
  -e NEXTAUTH_SECRET="$(openssl rand -base64 32)" \
  -e NEXTAUTH_URL="http://your-ec2-private-ip:3000" \
  langfuse/langfuse:latest
```

#### Option B: Fargate (production-grade)

Deploy as an ECS Fargate service in the same VPC as AgentCore. Use an internal ALB for the endpoint. Back with RDS PostgreSQL.

### Switching to Self-Hosted

1. Deploy Langfuse (Option A or B above)
2. Update the `LANGFUSE_BASE_URL` value in Secrets Manager:
   ```bash
   # Fetch current secret, update the URL, put it back
   aws secretsmanager get-secret-value \
     --secret-id openclaw-fsi-secrets \
     --query SecretString --output text | \
     jq '.LANGFUSE_BASE_URL = "http://your-langfuse-host:3000"' | \
     aws secretsmanager put-secret-value \
       --secret-id openclaw-fsi-secrets \
       --secret-string file:///dev/stdin
   ```
3. Update the SAM template `LangfuseBaseUrl` default (or pass as parameter on next `sam deploy`)
4. Redeploy AgentCore container (it reads secrets at startup)

That's it. The `LANGFUSE_BASE_URL` env var is the only thing that changes.

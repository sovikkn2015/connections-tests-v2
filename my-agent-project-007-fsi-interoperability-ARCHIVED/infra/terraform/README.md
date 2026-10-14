# Terraform — Project 007 FSI Platform VPC & PrivateLink

Private-only networking for the FSI data plane (Rule 22). MNPI data never traverses public internet.

## What This Creates

- VPC with private subnets only (one per AZ)
- NAT gateway for outbound-only access (package pulls, DNS)
- PrivateLink endpoints: Bedrock Runtime (Interface), S3 (Gateway), DynamoDB (Gateway)
- Security group restricting endpoint access to VPC CIDR

## Usage

```bash
cd infra/terraform

terraform init
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-east-1` | AWS region |
| `environment` | `dev` | Environment name |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR block |
| `private_subnet_cidrs` | 3 × /24 | Private subnet CIDRs |
| `cluster_name` | `007-fsi-platform` | EKS cluster name for subnet tags |

## Production Notes

- Enable remote state backend (S3) in `main.tf`
- Deploy one NAT gateway per AZ for HA
- Add VPC Flow Logs for audit compliance
- No credentials in Terraform files — use IAM roles or environment variables

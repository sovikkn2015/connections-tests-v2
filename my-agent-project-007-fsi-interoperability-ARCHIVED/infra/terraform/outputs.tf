output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (one per AZ)"
  value       = aws_subnet.private[*].id
}

output "bedrock_endpoint_id" {
  description = "Bedrock Runtime VPC endpoint ID"
  value       = aws_vpc_endpoint.bedrock_runtime.id
}

output "s3_endpoint_id" {
  description = "S3 Gateway VPC endpoint ID"
  value       = aws_vpc_endpoint.s3.id
}

output "dynamodb_endpoint_id" {
  description = "DynamoDB Gateway VPC endpoint ID"
  value       = aws_vpc_endpoint.dynamodb.id
}

output "vpc_endpoint_security_group_id" {
  description = "Security group ID for VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

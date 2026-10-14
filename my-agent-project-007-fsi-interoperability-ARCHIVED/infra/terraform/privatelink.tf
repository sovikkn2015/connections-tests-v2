# PrivateLink VPC Endpoints — Bedrock, S3, DynamoDB (Rule 22)
# All AWS service access stays on private network. No public internet for MNPI.

# Security group for VPC endpoints
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.environment}-007-fsi-vpce-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "HTTPS from VPC"
  }

  tags = {
    Name = "${var.environment}-007-fsi-vpce-sg"
  }
}

# Bedrock — LLM inference via PrivateLink (Sonnet for research, Haiku for routing)
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = {
    Name = "${var.environment}-007-fsi-bedrock-vpce"
  }
}

# S3 — Gateway endpoint (free, no PrivateLink charge)
# Used by M10 audit WORM tier (S3 Object Lock)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name = "${var.environment}-007-fsi-s3-vpce"
  }
}

# DynamoDB — Gateway endpoint (free)
# Used by M8 pipeline checkpoints in cloud topology
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name = "${var.environment}-007-fsi-dynamodb-vpce"
  }
}

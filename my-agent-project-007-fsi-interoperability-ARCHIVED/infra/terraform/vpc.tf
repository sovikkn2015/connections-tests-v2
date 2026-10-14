# VPC — Private subnets only for FSI data plane (Rule 22)
# No public subnets. NAT gateway for outbound-only access (package pulls, etc.).
# MNPI data never traverses public internet.

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.environment}-007-fsi-vpc"
  }
}

# Private subnets — one per AZ for HA
resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  # No public IPs — private only (Rule 22)
  map_public_ip_on_launch = false

  tags = {
    Name                                          = "${var.environment}-007-fsi-private-${var.availability_zones[count.index]}"
    "kubernetes.io/cluster/${var.cluster_name}"    = "shared"
    "kubernetes.io/role/internal-elb"              = "1"
  }
}

# Internet Gateway — required for NAT gateway outbound path
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.environment}-007-fsi-igw"
  }
}

# Single NAT gateway for outbound-only access (cost-optimized for dev/staging)
# Production: one NAT per AZ for HA
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.environment}-007-fsi-nat-eip"
  }
}

# Small subnet solely for NAT gateway placement (no workloads run here)
resource "aws_subnet" "nat" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.255.0/24"
  availability_zone = var.availability_zones[0]

  tags = {
    Name = "${var.environment}-007-fsi-nat-subnet"
  }
}

resource "aws_route_table" "nat_subnet" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.environment}-007-fsi-nat-rt"
  }
}

resource "aws_route_table_association" "nat_subnet" {
  subnet_id      = aws_subnet.nat.id
  route_table_id = aws_route_table.nat_subnet.id
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.nat.id

  tags = {
    Name = "${var.environment}-007-fsi-nat"
  }

  depends_on = [aws_internet_gateway.main]
}

# Route table for private subnets — outbound via NAT only
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "${var.environment}-007-fsi-private-rt"
  }
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

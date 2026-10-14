# Project 007 FSI Platform — Terraform Root Module
# Private-only networking for FSI data plane (Rule 22).
# No public subnets for MNPI workloads.

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — configure per environment
  # backend "s3" {
  #   bucket = "007-fsi-terraform-state"
  #   key    = "vpc/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "007-fsi-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

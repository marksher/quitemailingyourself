# Quitemailingyourself Infrastructure
# Complete infrastructure for the link organizer app

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment to use remote state (recommended for production)
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "quitemailingyourself/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "quitemailingyourself"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources for existing resources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Get current caller identity for unique naming
data "aws_caller_identity" "current" {}

# Local values for consistent naming
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# IAM Module
module "iam" {
  source = "./modules/iam"
  
  project_name = var.project_name
  environment  = var.environment
  s3_bucket_name = local.s3_bucket_name
}

# S3 Module
module "s3" {
  source = "./modules/s3"
  
  bucket_name = local.s3_bucket_name
  environment = var.environment
  
  tags = local.common_tags
}

# EC2 Module  
module "ec2" {
  source = "./modules/ec2"
  
  project_name           = var.project_name
  environment           = var.environment
  instance_type         = var.instance_type
  key_name              = var.key_name
  allowed_ssh_cidrs     = var.allowed_ssh_cidrs
  
  # From other modules
  instance_profile_name = module.iam.instance_profile_name
  subnet_id            = var.subnet_id
  
  # AMI
  ami_id = data.aws_ami.ubuntu.id
  
  tags = local.common_tags
}

# Generate unique bucket name using account ID
locals {
  s3_bucket_name = "${var.project_name}-${data.aws_caller_identity.current.account_id}"
}
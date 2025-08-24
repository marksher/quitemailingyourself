# Outputs for Quitemailingyourself Infrastructure

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = module.ec2.instance_id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = module.ec2.public_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = module.ec2.public_dns
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for DuckDB storage"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

output "iam_role_name" {
  description = "Name of the IAM role"
  value       = module.iam.role_name
}

output "iam_role_arn" {
  description = "ARN of the IAM role"
  value       = module.iam.role_arn
}

output "instance_profile_name" {
  description = "Name of the instance profile"
  value       = module.iam.instance_profile_name
}

output "security_group_id" {
  description = "ID of the security group"
  value       = module.ec2.security_group_id
}

output "app_url" {
  description = "URL to access the application"
  value       = "http://${module.ec2.public_ip}:8000"
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${module.ec2.public_ip}"
}

# Useful for GitHub Actions secrets
output "github_secrets" {
  description = "Values needed for GitHub Actions secrets"
  value = {
    EC2_HOST = module.ec2.public_ip
    EC2_USER = "ubuntu"
    # Note: EC2_SSH_KEY should be your private key content
  }
}
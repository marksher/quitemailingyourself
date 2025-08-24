# Quitemailingyourself Infrastructure

This directory contains Terraform configuration for deploying the complete Quitemailingyourself infrastructure on AWS.

## 🏗️ **What This Creates:**

- **EC2 Instance** - Ubuntu 22.04 with your app
- **IAM Role & Policy** - Secure S3 access without hardcoded keys
- **S3 Bucket** - DuckDB storage with encryption and lifecycle management
- **Security Groups** - Properly configured firewall rules
- **Instance Profile** - Links IAM role to EC2

## 📁 **Directory Structure:**

```
terraform/
├── main.tf                    # Main configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── modules/
│   ├── iam/                   # IAM roles and policies
│   ├── ec2/                   # EC2 instance and security groups
│   └── s3/                    # S3 bucket configuration
└── environments/
    ├── dev/terraform.tfvars   # Development settings
    └── prod/terraform.tfvars  # Production settings
```

## 🚀 **Quick Start:**

### 1. Prerequisites

```bash
# Install Terraform
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install terraform

# Configure AWS CLI
aws configure
# Enter your AWS Access Key ID, Secret Access Key, Region (us-east-1), and output format (json)

# Verify AWS access
aws sts get-caller-identity
```

### 2. Configure Your Settings

Edit the tfvars file for your environment:

```bash
# For development
cd terraform/
cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars
nano environments/dev/terraform.tfvars
```

**Required changes:**
- `key_name` - Your EC2 key pair name
- `allowed_ssh_cidrs` - Your IP address for SSH access

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Plan deployment (see what will be created)
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply changes
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### 4. Get Connection Info

```bash
# Get your instance IP and SSH command
terraform output

# Example output:
# app_url = "http://54.123.45.67:8000"
# ssh_command = "ssh -i ~/.ssh/your-key.pem ubuntu@54.123.45.67"
```

## 📋 **Management Commands:**

### Viewing Infrastructure Status
```bash
# See what's deployed
terraform show

# List all resources
terraform state list

# Get specific output
terraform output instance_public_ip
```

### Making Changes
```bash
# Plan changes
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply changes
terraform apply -var-file="environments/dev/terraform.tfvars"

# Refresh state
terraform refresh
```

### Destroying Infrastructure
```bash
# ⚠️ WARNING: This will delete everything!
terraform plan -destroy -var-file="environments/dev/terraform.tfvars"
terraform destroy -var-file="environments/dev/terraform.tfvars"
```

## 🔧 **Configuration Options:**

### Key Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `project_name` | Project name for resources | `quitemailingyourself` | |
| `environment` | Environment (dev/prod) | `dev` | |
| `instance_type` | EC2 instance size | `t3.micro` | `t3.small` |
| `key_name` | EC2 key pair name | *required* | `my-aws-key` |
| `allowed_ssh_cidrs` | IPs allowed to SSH | `["0.0.0.0/0"]` | `["1.2.3.4/32"]` |
| `root_volume_size` | Disk size in GB | `20` | `30` |

### Security Best Practices

**Development:**
- Use `t3.micro` instance (free tier)
- Restrict SSH to your IP only
- Use separate key pair from production

**Production:**
- Use `t3.small` or larger instance
- Restrict SSH to office/admin IPs only  
- Enable detailed monitoring
- Use separate AWS account if possible

## 🔄 **GitHub Actions Integration:**

After deployment, set these GitHub secrets:

```bash
# Get values from Terraform output
terraform output github_secrets

# Add to GitHub repo: Settings → Secrets → Actions
EC2_HOST = "your-instance-ip"
EC2_USER = "ubuntu"  
EC2_SSH_KEY = "contents-of-your-private-key-file"
```

## 📊 **Monitoring & Maintenance:**

### Health Checks
```bash
# Check if your app is running
curl http://$(terraform output -raw instance_public_ip):8000/health

# SSH into instance
$(terraform output -raw ssh_command)

# Check PM2 processes
pm2 status
pm2 logs
```

### Cost Monitoring
```bash
# Check AWS billing
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

## 🆘 **Troubleshooting:**

### Common Issues

**"InvalidKeyPair.NotFound"**
```bash
# Check your key pairs
aws ec2 describe-key-pairs

# Create new key pair if needed
aws ec2 create-key-pair --key-name my-new-key --query 'KeyMaterial' --output text > ~/.ssh/my-new-key.pem
chmod 400 ~/.ssh/my-new-key.pem
```

**"UnauthorizedOperation"**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify permissions
aws iam get-user
```

**Instance won't start**
```bash
# Check user data logs
ssh -i ~/.ssh/your-key.pem ubuntu@your-ip
sudo tail -f /var/log/user-data.log
```

### Getting Help

1. **Check Terraform docs**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
2. **AWS documentation**: https://docs.aws.amazon.com/
3. **Claude Code**: Ask me! I can help debug any issues 😊

## 🎯 **Next Steps:**

After infrastructure is deployed:

1. **SSH to your instance** using the provided command
2. **Run the setup script**: `wget https://raw.githubusercontent.com/marksher/quitemailingyourself/main/scripts/setup-ec2.sh && chmod +x setup-ec2.sh && ./setup-ec2.sh`
3. **Configure your app** by editing the `.env` file
4. **Set up GitHub Actions** with the provided secrets
5. **Deploy your app** via GitHub Actions or manual deployment

Your infrastructure is now ready for your amazing link organizer! 🎉
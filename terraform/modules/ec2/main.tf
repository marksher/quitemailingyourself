# EC2 resources for Quitemailingyourself

# Get default VPC if subnet_id not provided
data "aws_vpc" "default" {
  count   = var.subnet_id == null ? 1 : 0
  default = true
}

data "aws_subnet" "default" {
  count             = var.subnet_id == null ? 1 : 0
  vpc_id            = data.aws_vpc.default[0].id
  availability_zone = data.aws_availability_zones.available.names[0]
}

data "aws_availability_zones" "available" {
  state = "available"
}

# Security group for the application
resource "aws_security_group" "app_sg" {
  name_prefix = "${var.project_name}-${var.environment}-"
  description = "Security group for ${var.project_name} application"
  vpc_id      = var.subnet_id != null ? data.aws_subnet.selected[0].vpc_id : data.aws_vpc.default[0].id

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_ssh_cidrs
  }

  # HTTP access
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS access
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Application port
  ingress {
    description = "Application"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Get subnet data if provided
data "aws_subnet" "selected" {
  count = var.subnet_id != null ? 1 : 0
  id    = var.subnet_id
}

# EC2 Instance
resource "aws_instance" "app" {
  ami                     = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  subnet_id              = var.subnet_id != null ? var.subnet_id : data.aws_subnet.default[0].id
  iam_instance_profile   = var.instance_profile_name
  
  monitoring = var.enable_detailed_monitoring

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size
    encrypted   = true
    
    tags = merge(var.tags, {
      Name = "${var.project_name}-${var.environment}-root-volume"
    })
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    project_name = var.project_name
    environment  = var.environment
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-instance"
  })

  lifecycle {
    create_before_destroy = false
  }
}

# Elastic IP (optional - good for production)
resource "aws_eip" "app_eip" {
  count    = var.enable_elastic_ip ? 1 : 0
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-eip"
  })

  depends_on = [aws_instance.app]
}
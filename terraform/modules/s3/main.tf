# S3 resources for Quitemailingyourself DuckDB storage

# S3 bucket for DuckDB database storage
resource "aws_s3_bucket" "duckdb_storage" {
  bucket = var.bucket_name

  tags = merge(var.tags, {
    Name        = var.bucket_name
    Purpose     = "DuckDB storage for ${var.environment}"
    Environment = var.environment
  })

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "duckdb_versioning" {
  bucket = aws_s3_bucket.duckdb_storage.id
  
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "duckdb_encryption" {
  bucket = aws_s3_bucket.duckdb_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "duckdb_pab" {
  bucket = aws_s3_bucket.duckdb_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket lifecycle configuration for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "duckdb_lifecycle" {
  count  = var.enable_lifecycle ? 1 : 0
  bucket = aws_s3_bucket.duckdb_storage.id

  rule {
    id     = "cost_optimization"
    status = "Enabled"

    # Transition to IA after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_INFREQUENT_ACCESS"
    }

    # Transition to Glacier after 90 days (optional, for backups)
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Delete non-current versions after 30 days
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# S3 bucket notification for monitoring (optional)
resource "aws_s3_bucket_notification" "duckdb_notification" {
  count  = var.enable_notifications ? 1 : 0
  bucket = aws_s3_bucket.duckdb_storage.id

  # You can add CloudWatch, Lambda, or SQS notifications here
}

# Create initial folder structure
resource "aws_s3_object" "data_folder" {
  bucket = aws_s3_bucket.duckdb_storage.id
  key    = "data/"
  source = "/dev/null"

  tags = var.tags
}

resource "aws_s3_object" "backups_folder" {
  bucket = aws_s3_bucket.duckdb_storage.id
  key    = "backups/"
  source = "/dev/null"

  tags = var.tags
}
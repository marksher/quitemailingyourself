output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.duckdb_storage.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.duckdb_storage.arn
}

output "bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = aws_s3_bucket.duckdb_storage.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.duckdb_storage.bucket_regional_domain_name
}

output "bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.duckdb_storage.region
}
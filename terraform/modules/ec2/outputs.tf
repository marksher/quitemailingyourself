output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = var.enable_elastic_ip ? aws_eip.app_eip[0].public_ip : aws_instance.app.public_ip
}

output "private_ip" {
  description = "Private IP address of the instance"
  value       = aws_instance.app.private_ip
}

output "public_dns" {
  description = "Public DNS name of the instance"
  value       = aws_instance.app.public_dns
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.app_sg.id
}

output "availability_zone" {
  description = "Availability zone of the instance"
  value       = aws_instance.app.availability_zone
}

output "subnet_id" {
  description = "Subnet ID where the instance is launched"
  value       = aws_instance.app.subnet_id
}
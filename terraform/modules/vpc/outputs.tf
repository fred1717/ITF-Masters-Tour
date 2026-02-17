# -----------------------------------------------------------------------------
# VPC Module — Outputs
# -----------------------------------------------------------------------------

output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [aws_subnet.public_1.id, aws_subnet.public_2.id]
}

output "private_app_subnet_ids" {
  value = [aws_subnet.private_app_1.id, aws_subnet.private_app_2.id]
}

output "private_db_subnet_ids" {
  value = [aws_subnet.private_db_1.id, aws_subnet.private_db_2.id]
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "fargate_security_group_id" {
  value = aws_security_group.fargate.id
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}

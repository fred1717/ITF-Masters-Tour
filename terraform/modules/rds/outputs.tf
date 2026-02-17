# -----------------------------------------------------------------------------
# RDS Module — Outputs
# -----------------------------------------------------------------------------

output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "address" {
  value = aws_db_instance.this.address
}

output "arn" {
  value = aws_db_instance.this.arn
}

output "secret_arn" {
  description = "Secrets Manager ARN for DB credentials"
  value       = aws_secretsmanager_secret.db.arn
}

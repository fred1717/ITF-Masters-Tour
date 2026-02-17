# -----------------------------------------------------------------------------
# ITF Masters Tour — Outputs
# -----------------------------------------------------------------------------

output "app_url" {
  description = "Application URL"
  value       = "https://${var.domain_name}"
}

output "primary_alb_dns" {
  description = "Primary ALB DNS name (for debugging)"
  value       = module.primary_ecs.alb_dns_name
}

output "dr_alb_dns" {
  description = "DR ALB DNS name (for debugging)"
  value       = module.dr_ecs.alb_dns_name
}

output "primary_rds_endpoint" {
  description = "Primary RDS endpoint"
  value       = module.primary_rds.endpoint
}

output "dr_rds_endpoint" {
  description = "DR RDS endpoint (read replica)"
  value       = module.dr_rds.endpoint
}

output "ecr_repo_url" {
  description = "ECR repository URL for Docker push"
  value       = module.primary_ecs.ecr_repo_url
}

output "evidence_bucket" {
  description = "S3 bucket for evidence screenshots"
  value       = aws_s3_bucket.evidence.bucket
}

output "health_check_id" {
  description = "Route53 health check ID"
  value       = module.dns.health_check_id
}

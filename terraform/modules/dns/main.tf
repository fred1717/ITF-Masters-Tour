# Declare provider requirement so Terraform resolves the alias passed by the root module

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

# -----------------------------------------------------------------------------
# DNS Module — Route53 Health Check + Failover Routing
# -----------------------------------------------------------------------------

# --- Health Check on Primary ALB ---

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_alb_dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/tournaments"
  failure_threshold = 3
  request_interval  = 30

  tags = { Name = "${var.project_name}-primary-health-check" }
}

# --- Failover DNS Records ---

# Primary record — active when health check passes
resource "aws_route53_record" "primary" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary.id

  alias {
    name                   = var.primary_alb_dns_name
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}

# Secondary record — activated on primary health check failure
resource "aws_route53_record" "secondary" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary"

  alias {
    name                   = var.dr_alb_dns_name
    zone_id                = var.dr_alb_zone_id
    evaluate_target_health = true
  }
}

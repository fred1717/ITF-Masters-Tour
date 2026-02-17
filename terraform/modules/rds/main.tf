# Declare provider requirement so Terraform resolves the alias passed by the root module

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

# -----------------------------------------------------------------------------
# RDS Module — PostgreSQL 16 (Primary or Cross-Region Replica)
# Secrets Manager created in every region so Fargate can read locally.
# -----------------------------------------------------------------------------

locals {
  tag = "${var.project_name}-${var.region_label}"
}

# --- DB Subnet Group ---

resource "aws_db_subnet_group" "this" {
  name       = "${local.tag}-db-subnets"
  subnet_ids = var.private_db_subnet_ids
  tags       = { Name = "${local.tag}-db-subnets" }
}

# --- Secrets Manager (both regions — Fargate reads locally via VPC Endpoint) -

resource "aws_secretsmanager_secret" "db" {
  name        = "${local.tag}-db-credentials"
  description = "RDS PostgreSQL credentials for ${var.project_name}"
  tags        = { Name = "${local.tag}-db-secret" }
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    dbname   = var.db_name
    port     = 5432
  })
}

# --- KMS key for cross-region replica (default key is region-specific) ---

resource "aws_kms_key" "rds" {
  count       = var.is_replica ? 1 : 0
  description = "${local.tag}-rds-encryption-key"
}

# --- RDS Instance ---

resource "aws_db_instance" "this" {
  identifier     = "${local.tag}-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  # Primary-only settings
  db_name  = var.is_replica ? null : var.db_name
  username = var.is_replica ? null : var.db_username
  password = var.is_replica ? null : var.db_password

  # Replica settings
  replicate_source_db = var.is_replica ? var.replicate_source_db : null

  # Storage
  allocated_storage = var.is_replica ? null : 20
  storage_type      = "gp3"
  storage_encrypted = true
  kms_key_id        = var.is_replica ? aws_kms_key.rds[0].arn : null

  # Network
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.rds_security_group_id]
  publicly_accessible    = false
  multi_az               = var.is_replica ? false : true

  # Maintenance
  backup_retention_period = var.is_replica ? 0 : 1
  skip_final_snapshot     = true
  deletion_protection     = false

  tags = { Name = "${local.tag}-postgres" }
}

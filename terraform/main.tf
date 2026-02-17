# -----------------------------------------------------------------------------
# ITF Masters Tour — Main Configuration
# Dual-region DR deployment: Fargate + ALB + RDS PostgreSQL + Route53
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# --- Providers ---------------------------------------------------------------

provider "aws" {
  region = var.primary_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "terraform"
      Environment = "portfolio"
    }
  }
}

provider "aws" {
  alias  = "dr"
  region = var.dr_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "terraform"
      Environment = "portfolio"
    }
  }
}

# =============================================================================
# Shared — DB password generated once, stored in both regions
# =============================================================================

resource "random_password" "db" {
  length  = 24
  special = false
}

# =============================================================================
# PRIMARY REGION
# =============================================================================

module "primary_vpc" {
  source = "./modules/vpc"

  project_name   = var.project_name
  vpc_cidr       = var.primary_vpc_cidr
  region_label   = "primary"
  container_port = var.container_port
}

module "primary_rds" {
  source = "./modules/rds"

  project_name      = var.project_name
  region_label      = "primary"
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = random_password.db.result
  db_instance_class = var.db_instance_class

  private_db_subnet_ids = module.primary_vpc.private_db_subnet_ids
  rds_security_group_id = module.primary_vpc.rds_security_group_id

  is_replica = false
}

module "primary_ecs" {
  source = "./modules/ecs"

  project_name   = var.project_name
  region_label   = "primary"
  container_port = var.container_port
  fargate_cpu    = var.fargate_cpu
  fargate_memory = var.fargate_memory
  flask_image_tag = var.flask_image_tag

  vpc_id                    = module.primary_vpc.vpc_id
  public_subnet_ids         = module.primary_vpc.public_subnet_ids
  private_app_subnet_ids    = module.primary_vpc.private_app_subnet_ids
  alb_security_group_id     = module.primary_vpc.alb_security_group_id
  fargate_security_group_id = module.primary_vpc.fargate_security_group_id

  db_host       = module.primary_rds.address
  db_name       = var.db_name
  db_secret_arn = module.primary_rds.secret_arn

  create_ecr  = true
  domain_name    = var.domain_name
  hosted_zone_id = var.hosted_zone_id
  is_standby     = false
}

# =============================================================================
# DR REGION
# =============================================================================

module "dr_vpc" {
  source = "./modules/vpc"

  providers = { aws = aws.dr }

  project_name   = var.project_name
  vpc_cidr       = var.dr_vpc_cidr
  region_label   = "dr"
  container_port = var.container_port
}

module "dr_rds" {
  source = "./modules/rds"

  providers = { aws = aws.dr }

  project_name      = var.project_name
  region_label      = "dr"
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = random_password.db.result
  db_instance_class = var.db_instance_class

  private_db_subnet_ids = module.dr_vpc.private_db_subnet_ids
  rds_security_group_id = module.dr_vpc.rds_security_group_id

  is_replica          = true
  replicate_source_db = module.primary_rds.arn
}

module "dr_ecs" {
  source = "./modules/ecs"

  providers = { aws = aws.dr }

  project_name   = var.project_name
  region_label   = "dr"
  container_port = var.container_port
  fargate_cpu    = var.fargate_cpu
  fargate_memory = var.fargate_memory
  flask_image_tag = var.flask_image_tag

  vpc_id                    = module.dr_vpc.vpc_id
  public_subnet_ids         = module.dr_vpc.public_subnet_ids
  private_app_subnet_ids    = module.dr_vpc.private_app_subnet_ids
  alb_security_group_id     = module.dr_vpc.alb_security_group_id
  fargate_security_group_id = module.dr_vpc.fargate_security_group_id

  db_host       = module.dr_rds.address
  db_name       = var.db_name
  db_secret_arn = module.dr_rds.secret_arn

  create_ecr     = false
  ecr_repo_url   = "180294215772.dkr.ecr.us-west-2.amazonaws.com/itf-masters-tour"
  domain_name    = var.domain_name
  hosted_zone_id = var.hosted_zone_id
  is_standby     = true
}

# =============================================================================
# DNS — Route53 Failover + Health Check
# =============================================================================

module "dns" {
  source = "./modules/dns"

  project_name = var.project_name
  domain_name  = var.domain_name
  hosted_zone_id = var.hosted_zone_id

  primary_alb_dns_name = module.primary_ecs.alb_dns_name
  primary_alb_zone_id  = module.primary_ecs.alb_zone_id
  dr_alb_dns_name      = module.dr_ecs.alb_dns_name
  dr_alb_zone_id       = module.dr_ecs.alb_zone_id
}

# =============================================================================
# S3 — Evidence Storage (persists after teardown)
# =============================================================================

resource "aws_s3_bucket" "evidence" {
  bucket        = "${var.project_name}-evidence"
  force_destroy = true

  tags = { Name = "${var.project_name}-evidence" }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

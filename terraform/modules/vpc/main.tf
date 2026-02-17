# Declare provider requirement so Terraform resolves the alias passed by the root module

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

# -----------------------------------------------------------------------------
# VPC Module — Networking, Security Groups, VPC Endpoints
# -----------------------------------------------------------------------------

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  az1    = data.aws_availability_zones.available.names[0]
  az2    = data.aws_availability_zones.available.names[1]
  tag    = "${var.project_name}-${var.region_label}"
  region = data.aws_region.current.name
}

# --- VPC ---

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = local.tag }
}

# --- Internet Gateway (for ALB in public subnets) ---

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.tag}-igw" }
}

# === SUBNETS =================================================================

resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 1)
  availability_zone       = local.az1
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.tag}-public-1" }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 2)
  availability_zone       = local.az2
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.tag}-public-2" }
}

resource "aws_subnet" "private_app_1" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 10)
  availability_zone = local.az1
  tags              = { Name = "${local.tag}-private-app-1" }
}

resource "aws_subnet" "private_app_2" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 11)
  availability_zone = local.az2
  tags              = { Name = "${local.tag}-private-app-2" }
}

resource "aws_subnet" "private_db_1" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 20)
  availability_zone = local.az1
  tags              = { Name = "${local.tag}-private-db-1" }
}

resource "aws_subnet" "private_db_2" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 21)
  availability_zone = local.az2
  tags              = { Name = "${local.tag}-private-db-2" }
}

# === ROUTE TABLES ============================================================

# Public route table — routes to IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.tag}-public-rt" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

# Private route table — local only (no NAT, VPC endpoints handle AWS services)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.tag}-private-rt" }
}

resource "aws_route_table_association" "private_app_1" {
  subnet_id      = aws_subnet.private_app_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_app_2" {
  subnet_id      = aws_subnet.private_app_2.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_db_1" {
  subnet_id      = aws_subnet.private_db_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_db_2" {
  subnet_id      = aws_subnet.private_db_2.id
  route_table_id = aws_route_table.private.id
}

# === SECURITY GROUPS =========================================================

# ALB — accepts HTTPS from the internet
resource "aws_security_group" "alb" {
  name_prefix = "${local.tag}-alb-"
  vpc_id      = aws_vpc.this.id
  description = "ALB: inbound HTTPS from internet"

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.tag}-alb-sg" }

  lifecycle { create_before_destroy = true }
}

# Fargate — accepts traffic only from ALB
resource "aws_security_group" "fargate" {
  name_prefix = "${local.tag}-fargate-"
  vpc_id      = aws_vpc.this.id
  description = "Fargate: inbound from ALB only"

  ingress {
    description     = "Flask from ALB"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.tag}-fargate-sg" }

  lifecycle { create_before_destroy = true }
}

# RDS — accepts traffic only from Fargate
resource "aws_security_group" "rds" {
  name_prefix = "${local.tag}-rds-"
  vpc_id      = aws_vpc.this.id
  description = "RDS: inbound from Fargate only"

  ingress {
    description     = "PostgreSQL from Fargate"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.fargate.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.tag}-rds-sg" }

  lifecycle { create_before_destroy = true }
}

# VPC Endpoints — accepts HTTPS from Fargate
resource "aws_security_group" "vpce" {
  name_prefix = "${local.tag}-vpce-"
  vpc_id      = aws_vpc.this.id
  description = "VPC Endpoints: HTTPS from Fargate"

  ingress {
    description     = "HTTPS from Fargate"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.fargate.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.tag}-vpce-sg" }

  lifecycle { create_before_destroy = true }
}

# === VPC ENDPOINTS (replace NAT Gateway — saves ~$15/month) ==================

locals {
  private_app_subnet_ids = [
    aws_subnet.private_app_1.id,
    aws_subnet.private_app_2.id,
  ]
}

# Secrets Manager — Fargate retrieves DB credentials at startup
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_app_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = { Name = "${local.tag}-vpce-secrets" }
}

# CloudWatch Logs — Fargate sends container logs
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_app_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = { Name = "${local.tag}-vpce-logs" }
}

# ECR API — Fargate authenticates with ECR
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_app_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = { Name = "${local.tag}-vpce-ecr-api" }
}

# ECR Docker — Fargate pulls container image layers
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_app_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = { Name = "${local.tag}-vpce-ecr-dkr" }
}

# SSM Messages — required for ECS Exec (interactive container access)
resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${local.region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_app_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = { Name = "${local.tag}-vpce-ssmmessages" }
}

# S3 Gateway — ECR image layers stored in S3 (FREE)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = { Name = "${local.tag}-vpce-s3" }
}

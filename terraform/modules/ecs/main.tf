# Declare provider requirement so Terraform resolves the alias passed by the root module

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

# -----------------------------------------------------------------------------
# ECS Module — Fargate + ALB + ACM + IAM
# -----------------------------------------------------------------------------

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  tag      = "${var.project_name}-${var.region_label}"
  repo_url = var.create_ecr ? aws_ecr_repository.this[0].repository_url : var.ecr_repo_url
}

# === ECR (primary region only) ===============================================

resource "aws_ecr_repository" "this" {
  count                = var.create_ecr ? 1 : 0
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = { Name = "${local.tag}-ecr" }
}

# === CloudWatch Log Group ====================================================

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${local.tag}"
  retention_in_days = 3

  tags = { Name = "${local.tag}-logs" }
}

# === IAM — Task Execution Role ===============================================
# Grants Fargate permission to pull images, read secrets, write logs

resource "aws_iam_role" "execution" {
  name = "${local.tag}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = { Name = "${local.tag}-ecs-execution" }
}

resource "aws_iam_role_policy" "execution" {
  name = "${local.tag}-ecs-execution-policy"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.db_secret_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = ["${aws_cloudwatch_log_group.this.arn}:*"]
      },
    ]
  })
}

# === IAM — Task Role (minimal — DB access is network-level) ==================

resource "aws_iam_role" "task" {
  name = "${local.tag}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = { Name = "${local.tag}-ecs-task" }
}

# Grant Fargate task access to SSM (ECS Exec) and S3 (database dump download)
resource "aws_iam_role_policy" "task" {
  name = "${local.tag}-ecs-task-policy"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["arn:aws:s3:::${var.project_name}-evidence/*"]
      },
    ]
  })
}

# === ECS Cluster =============================================================

resource "aws_ecs_cluster" "this" {
  name = local.tag
  tags = { Name = local.tag }
}

# === Task Definition =========================================================

resource "aws_ecs_task_definition" "this" {
  family                   = local.tag
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.fargate_cpu
  memory                   = var.fargate_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "flask"
    image     = "${local.repo_url}:${var.flask_image_tag}"
    essential = true

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    environment = [
      { name = "DB_HOST", value = var.db_host },
      { name = "DB_PORT", value = "5432" },
      { name = "DB_NAME", value = var.db_name },
    ]

    secrets = [
      {
        name      = "DB_USER"
        valueFrom = "${var.db_secret_arn}:username::"
      },
      {
        name      = "DB_PASSWORD"
        valueFrom = "${var.db_secret_arn}:password::"
      },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.this.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "flask"
      }
    }
  }])

  tags = { Name = local.tag }
}

# === ACM Certificate =========================================================

resource "aws_acm_certificate" "this" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = { Name = "${local.tag}-cert" }

  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.this.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  allow_overwrite = true
  zone_id         = var.hosted_zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# === ALB =====================================================================

resource "aws_lb" "this" {
  name               = "${local.tag}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  tags = { Name = "${local.tag}-alb" }
}

resource "aws_lb_target_group" "this" {
  name        = "${local.tag}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/tournaments"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }

  tags = { Name = "${local.tag}-tg" }
}

# HTTPS listener — forward to Fargate
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.this.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

# HTTP listener — redirect to HTTPS
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# === ECS Service =============================================================

resource "aws_ecs_service" "this" {
  name            = "${local.tag}-service"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  launch_type     = "FARGATE"
  # Enable ECS Exec for interactive container access (pg_restore, debugging)
  enable_execute_command = true
  desired_count   = var.is_standby ? 0 : 1

  network_configuration {
    subnets          = var.private_app_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = "flask"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.https]

  tags = { Name = "${local.tag}-service" }
}

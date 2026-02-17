# -----------------------------------------------------------------------------
# ECS Module — Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  type = string
}

variable "region_label" {
  type = string
}

variable "container_port" {
  type = number
}

variable "fargate_cpu" {
  type = number
}

variable "fargate_memory" {
  type = number
}

variable "flask_image_tag" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_app_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "fargate_security_group_id" {
  type = string
}

variable "db_host" {
  description = "RDS endpoint hostname"
  type        = string
}

variable "db_name" {
  type = string
}

variable "db_secret_arn" {
  description = "Secrets Manager ARN containing DB credentials"
  type        = string
}

variable "ecr_repo_url" {
  description = "ECR repository URL (passed from primary to DR)"
  type        = string
  default     = ""
}

variable "create_ecr" {
  description = "Whether to create ECR repository (true for primary only)"
  type        = bool
  default     = false
}

variable "domain_name" {
  type = string
}

variable "hosted_zone_id" {
  type = string
}

variable "is_standby" {
  description = "If true, the ECS service desired count is 0 (DR standby)"
  type        = bool
  default     = false
}

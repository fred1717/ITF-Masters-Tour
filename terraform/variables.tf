# -----------------------------------------------------------------------------
# ITF Masters Tour — Terraform Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "itf-masters-tour"
}

variable "primary_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "dr_region" {
  description = "Disaster recovery AWS region"
  type        = string
  default     = "us-west-2"
}

variable "domain_name" {
  description = "Fully qualified domain name for the application"
  type        = string
  default     = "awscloudcase.com"
}

variable "hosted_zone_id" {
  description = "Existing Route53 hosted zone ID for cloudcase.com"
  type        = string
}

# --- Networking ---

variable "primary_vpc_cidr" {
  description = "CIDR block for the primary VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "dr_vpc_cidr" {
  description = "CIDR block for the DR VPC"
  type        = string
  default     = "10.1.0.0/16"
}

# --- Database ---

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "itf_tournament"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "itfuser"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

# --- Compute ---

variable "container_port" {
  description = "Port the Flask container listens on"
  type        = number
  default     = 5000
}

variable "fargate_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "fargate_memory" {
  description = "Fargate task memory in MB"
  type        = number
  default     = 512
}

variable "flask_image_tag" {
  description = "Docker image tag for the Flask application"
  type        = string
  default     = "latest"
}

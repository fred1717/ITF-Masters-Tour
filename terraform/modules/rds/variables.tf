# -----------------------------------------------------------------------------
# RDS Module — Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  type = string
}

variable "region_label" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "db_password" {
  description = "Database master password (generated in main.tf)"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  type = string
}

variable "private_db_subnet_ids" {
  type = list(string)
}

variable "rds_security_group_id" {
  type = string
}

variable "is_replica" {
  description = "If true, creates a cross-region read replica instead of a primary"
  type        = bool
  default     = false
}

variable "replicate_source_db" {
  description = "ARN of the primary RDS instance (required when is_replica = true)"
  type        = string
  default     = ""
}

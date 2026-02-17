# -----------------------------------------------------------------------------
# VPC Module — Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "region_label" {
  description = "Label for tagging: primary or dr"
  type        = string
}

variable "container_port" {
  type    = number
  default = 5000
}

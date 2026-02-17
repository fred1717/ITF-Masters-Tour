# -----------------------------------------------------------------------------
# DNS Module — Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  type = string
}

variable "domain_name" {
  type = string
}

variable "hosted_zone_id" {
  type = string
}

variable "primary_alb_dns_name" {
  type = string
}

variable "primary_alb_zone_id" {
  type = string
}

variable "dr_alb_dns_name" {
  type = string
}

variable "dr_alb_zone_id" {
  type = string
}

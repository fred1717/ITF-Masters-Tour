# -----------------------------------------------------------------------------
# ITF Masters Tour — Terraform Variables (Example)
# Copy to terraform.tfvars and fill in the hosted_zone_id
# -----------------------------------------------------------------------------

project_name     = "itf-masters-tour"
primary_region   = "us-east-1"
dr_region        = "us-west-2"

domain_name      = "awscloudcase.com"
hosted_zone_id   = "Z023982439K9GBELWF4Z4"

primary_vpc_cidr = "10.0.0.0/16"
dr_vpc_cidr      = "10.1.0.0/16"

db_name           = "itf_tournament"
db_username       = "itfuser"
db_instance_class = "db.t4g.micro"

container_port  = 5000
fargate_cpu     = 256       # 0.25 vCPU
fargate_memory  = 512       # 0.5 GB
flask_image_tag = "latest"

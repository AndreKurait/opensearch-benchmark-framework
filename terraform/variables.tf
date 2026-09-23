variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "osb-bench"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

# The benchmark pins every node to ONE availability zone, so that zone must have
# a subnet. Relying on the first three available AZs is not safe: in some regions
# only a single AZ offers all nine 8th-gen instance types (eu-west-1c), and that
# AZ is not necessarily among the first three returned.
variable "bench_az" {
  description = "Availability zone the benchmark pins all nodes to. Must have a subnet."
  type        = string
  default     = ""
}

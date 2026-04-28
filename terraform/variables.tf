variable "region" {
  description = "AWS region for deploying resources - affects data residency, compliance, and service availability. Choose based on your security and performance requirements."
  type        = string
  default     = "us-east-1"
  validation {
    condition = contains([
      "us-east-1", "us-east-2", "us-west-1", "us-west-2",
      "eu-west-1", "eu-central-1", "ap-southeast-1", "ap-northeast-1"
    ], var.region)
    error_message = "Region must be a valid AWS region. For production, consider regions with additional security certifications like FedRAMP."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster - must be lowercase, alphanumeric with hyphens, max 38 characters. Used for resource naming and security group identification."
  type        = string
  default     = "micro-segmentation-cluster"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.cluster_name)) && length(var.cluster_name) <= 38
    error_message = "Cluster name must be lowercase alphanumeric with hyphens only, max 38 characters."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC - defines the private network range. Use RFC 1918 private addresses (/16 recommended for EKS). Affects subnet planning and security group rules."
  type        = string
  default     = "10.0.0.0/16"
  validation {
    condition = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}\\/(1[6-9]|2[0-4])$", var.vpc_cidr))
    error_message = "VPC CIDR must be a valid private IP range with /16-/24 prefix for proper subnet allocation."
  }
}

variable "subnet_cidrs" {
  description = "CIDR blocks for subnets - must be within VPC CIDR range and provide high availability across AZs. /24 subnets recommended for EKS node groups."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  validation {
    condition = length(var.subnet_cidrs) >= 2 && alltrue([
      for cidr in var.subnet_cidrs : can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}\\/2[4-8]$", cidr))
    ])
    error_message = "Must provide at least 2 subnet CIDRs with /24-/28 prefix for proper network segmentation and availability."
  }
}
 
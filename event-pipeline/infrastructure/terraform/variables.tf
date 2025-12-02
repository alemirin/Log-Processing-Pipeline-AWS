# infrastructure/terraform/variables.tf

variable "environment" {
  description = "Deployment environment (local or aws)"
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["local", "aws"], var.environment)
    error_message = "Environment must be 'local' or 'aws'."
  }
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack endpoint URL"
  type        = string
  default     = "http://host.docker.internal:4566"
}

variable "lambda_endpoint" {
  description = "Endpoint URL that Lambda functions use to reach LocalStack (host.docker.internal for Docker)"
  type        = string
  default     = ""
}

variable "lambda_memory_size" {
  description = "Memory size for Lambda functions (MB)"
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Timeout for Lambda functions (seconds)"
  type        = number
  default     = 30
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout (seconds)"
  type        = number
  default     = 60
}

variable "sqs_max_receive_count" {
  description = "Max receives before sending to DLQ"
  type        = number
  default     = 3
}

variable "dynamodb_ttl_days" {
  description = "Days to retain results in DynamoDB"
  type        = number
  default     = 7
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "event-pipeline"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project   = "event-pipeline"
    ManagedBy = "terraform"
  }
}

variable "use_lab_role" {
  description = "Whether to use AWS Academy LabRole instead of creating IAM roles"
  type        = bool
  default     = false
}

variable "lab_role_arn" {
  description = "ARN of the AWS Academy LabRole (required if use_lab_role is true)"
  type        = string
  default     = ""
}
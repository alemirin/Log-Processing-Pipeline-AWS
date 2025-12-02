# infrastructure/terraform/main.tf

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # LocalStack-specific configuration
  access_key = var.environment == "local" ? "test" : null
  secret_key = var.environment == "local" ? "test" : null

  # LocalStack doesn't validate credentials
  skip_credentials_validation = var.environment == "local"
  skip_metadata_api_check     = var.environment == "local"
  skip_requesting_account_id  = var.environment == "local"

  s3_use_path_style = var.environment == "local"

  # LocalStack configuration
  dynamic "endpoints" {
    for_each = var.environment == "local" ? [1] : []
    content {
      s3       = var.localstack_endpoint
      sqs      = var.localstack_endpoint
      lambda   = var.localstack_endpoint
      dynamodb = var.localstack_endpoint
      iam      = var.localstack_endpoint
      cloudwatchlogs = var.localstack_endpoint
      cloudwatch     = var.localstack_endpoint
      sts            = var.localstack_endpoint
    }
  }

  
}
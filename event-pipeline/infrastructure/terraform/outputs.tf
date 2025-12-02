# infrastructure/terraform/outputs.tf

output "s3_bucket_name" {
  description = "Name of the S3 upload bucket"
  value       = aws_s3_bucket.upload_bucket.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 upload bucket"
  value       = aws_s3_bucket.upload_bucket.arn
}

output "sqs_queue_url" {
  description = "URL of the SQS processing queue"
  value       = aws_sqs_queue.processing_queue.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS processing queue"
  value       = aws_sqs_queue.processing_queue.arn
}

output "dlq_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.dlq.url
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB results table"
  value       = aws_dynamodb_table.results.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB results table"
  value       = aws_dynamodb_table.results.arn
}

output "trigger_lambda_arn" {
  description = "ARN of the trigger Lambda function"
  value       = aws_lambda_function.trigger.arn
}

output "worker_lambda_arn" {
  description = "ARN of the worker Lambda function"
  value       = aws_lambda_function.worker.arn
}

output "environment" {
  description = "Deployment environment"
  value       = var.environment
}
# infrastructure/terraform/lambda.tf

# IAM Role for Lambda Functions
resource "aws_iam_role" "lambda_role" {
  count = var.use_lab_role ? 0 : 1
  name = "${var.project_name}-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  count = var.use_lab_role ? 0 : 1
  name = "${var.project_name}-lambda-policy-${var.environment}"
  role = aws_iam_role.lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:HeadObject"
        ]
        Resource = "${aws_s3_bucket.upload_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.processing_queue.arn,
          aws_sqs_queue.dlq.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.results.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

locals {
  lambda_role_arn = var.use_lab_role ? var.lab_role_arn : aws_iam_role.lambda_role[0].arn
}

# Trigger Lambda Function
resource "aws_lambda_function" "trigger" {
  filename         = "${path.module}/../../build/trigger.zip"
  function_name    = "${var.project_name}-trigger-${var.environment}"
  role             = local.lambda_role_arn
  handler          = "bootstrap"
  source_code_hash = filebase64sha256("${path.module}/../../build/trigger.zip")
  runtime          = "provided.al2023"
  architectures    = ["arm64"]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout

  environment {
    variables = {
      QUEUE_URL       = aws_sqs_queue.processing_queue.url
      ENVIRONMENT     = var.environment
      AWS_ENDPOINT_URL = var.environment == "local" ? var.lambda_endpoint : ""
    }
  }

  tags = var.tags
}

# Worker Lambda Function
resource "aws_lambda_function" "worker" {
  filename         = "${path.module}/../../build/worker.zip"
  function_name    = "${var.project_name}-worker-${var.environment}"
  role             = local.lambda_role_arn
  handler          = "bootstrap"
  source_code_hash = filebase64sha256("${path.module}/../../build/worker.zip")
  runtime          = "provided.al2023"
  architectures    = ["arm64"]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout

  environment {
    variables = {
      DYNAMODB_TABLE   = aws_dynamodb_table.results.name
      ENVIRONMENT      = var.environment
      AWS_ENDPOINT_URL = var.environment == "local" ? var.lambda_endpoint : ""
    }
  }

  tags = var.tags
}

# S3 trigger permission
resource "aws_lambda_permission" "s3_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.upload_bucket.arn
}

# S3 bucket notification
resource "aws_s3_bucket_notification" "trigger_notification" {
  bucket = aws_s3_bucket.upload_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "logs/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.s3_trigger]
}

# SQS trigger for worker
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.processing_queue.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 10
  enabled          = true
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "trigger_logs" {
  count             = var.environment == "aws" ? 1 : 0
  name              = "/aws/lambda/${aws_lambda_function.trigger.function_name}"
  retention_in_days = 7
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "worker_logs" {
  count             = var.environment == "aws" ? 1 : 0
  name              = "/aws/lambda/${aws_lambda_function.worker.function_name}"
  retention_in_days = 7
  tags              = var.tags
}

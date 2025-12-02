# Makefile for Event-Driven Processing Pipeline

.PHONY: all build build-lambda clean deps help
.PHONY: localstack-up localstack-down deploy-local destroy-local
.PHONY: deploy-aws destroy-aws
.PHONY: test-upload-local test-upload-aws
.PHONY: view-results-local view-results-aws
.PHONY: run-tests-local run-tests-aws generate-charts full-analysis
.PHONY: full-local clean-all open-charts workspace-status

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOTEST=$(GOCMD) test
GOMOD=$(GOCMD) mod

# Build output
BUILD_DIR=build

# Default target
all: build-lambda

#==============================================================================
# HELP
#==============================================================================

help:
	@echo "Event-Driven Processing Pipeline - Available Targets"
	@echo ""
	@echo "Building:"
	@echo "  build-lambda     - Build Lambda deployment packages (zip files)"
	@echo "  clean            - Remove build artifacts"
	@echo ""
	@echo "LocalStack:"
	@echo "  localstack-up    - Start LocalStack containers"
	@echo "  localstack-down  - Stop LocalStack containers"
	@echo "  deploy-local     - Deploy infrastructure to LocalStack"
	@echo "  destroy-local    - Destroy LocalStack infrastructure"
	@echo ""
	@echo "AWS:"
	@echo "  deploy-aws       - Deploy infrastructure to AWS Learner Lab"
	@echo "  destroy-aws      - Destroy AWS infrastructure"
	@echo ""
	@echo "Manual Testing:"
	@echo "  test-upload-local  - Upload sample file to LocalStack"
	@echo "  test-upload-aws    - Upload sample file to AWS"
	@echo "  view-results-local - View DynamoDB results (LocalStack)"
	@echo "  view-results-aws   - View DynamoDB results (AWS)"
	@echo ""
	@echo "Analysis:"
	@echo "  run-tests-local  - Run systematic tests on LocalStack"
	@echo "  run-tests-aws    - Run systematic tests on AWS"
	@echo "  generate-charts  - Generate analysis charts from test results"
	@echo "  full-analysis    - Run tests on both environments + generate charts"
	@echo ""
	@echo "Workflows:"
	@echo "  full-local       - Start LocalStack, deploy, and run tests"
	@echo "  clean-all        - Clean artifacts, destroy infra, stop LocalStack"
	@echo ""
	@echo "Utility:"
	@echo "  workspace-status - Show current Terraform workspace"

#==============================================================================
# BUILDING
#==============================================================================

# Download dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

# Build for local development
build: deps
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) -o $(BUILD_DIR)/trigger ./cmd/trigger
	$(GOBUILD) -o $(BUILD_DIR)/worker ./cmd/worker
	@echo "Built binaries in $(BUILD_DIR)/"

# Build for Lambda (Linux ARM64)
build-lambda: deps
	@mkdir -p $(BUILD_DIR)
	@echo "Building trigger Lambda..."
	GOOS=linux GOARCH=arm64 $(GOBUILD) -tags lambda.norpc -o $(BUILD_DIR)/bootstrap ./cmd/trigger
	cd $(BUILD_DIR) && zip trigger.zip bootstrap && rm bootstrap
	@echo "Building worker Lambda..."
	GOOS=linux GOARCH=arm64 $(GOBUILD) -tags lambda.norpc -o $(BUILD_DIR)/bootstrap ./cmd/worker
	cd $(BUILD_DIR) && zip worker.zip bootstrap && rm bootstrap
	@echo "Lambda packages created in $(BUILD_DIR)/"
	@ls -la $(BUILD_DIR)/*.zip

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)
	rm -f test/data/generated_*.json
	@echo "Cleaned build artifacts"

#==============================================================================
# LOCALSTACK
#==============================================================================

# Start LocalStack
localstack-up:
	@echo "Starting LocalStack..."
	cd infrastructure/localstack && docker-compose up -d
	@echo "Waiting for LocalStack to be ready..."
	@sleep 15
	@curl -s http://localhost:4566/_localstack/health | head -1
	@echo "\nLocalStack is ready!"

# Stop LocalStack
localstack-down:
	@echo "Stopping LocalStack..."
	cd infrastructure/localstack && docker-compose down -v
	@echo "LocalStack stopped"

# Deploy to LocalStack
deploy-local: build-lambda
	@echo "Deploying to LocalStack..."
	cd infrastructure/terraform && \
	    terraform workspace select local || terraform workspace new local && \
		terraform init && \
		terraform apply -var-file="local.tfvars" -auto-approve
	@echo ""
	@echo "=========================================="
	@echo "Localstack Deployment complete! Set these environment variables:"
	@echo "=========================================="
	@echo 'export AWS_ENDPOINT_URL="http://localhost:4566"'
	@echo 'export AWS_ACCESS_KEY_ID="test"'
	@echo 'export AWS_SECRET_ACCESS_KEY="test"'
	@echo 'export AWS_DEFAULT_REGION="us-east-1"'
	@echo 'export S3_BUCKET=$$(cd infrastructure/terraform && terraform output -raw s3_bucket_name)'
	@echo 'export DYNAMODB_TABLE=$$(cd infrastructure/terraform && terraform output -raw dynamodb_table_name)'

# Destroy LocalStack resources
destroy-local:
	@echo "Destroying LocalStack infrastructure..."
	cd infrastructure/terraform && \
	    terraform workspace select local && \
		terraform destroy -var-file="local.tfvars" -auto-approve
	@echo "LocalStack infrastructure destroyed"

#==============================================================================
# AWS LEARNER LAB
#==============================================================================

# Deploy to AWS Learner Lab
deploy-aws: build-lambda
	@echo "Deploying to AWS Learner Lab..."
	@echo "Make sure you have:"
	@echo "  1. Configured AWS CLI with Learner Lab credentials"
	@echo "  2. Updated aws-learner-lab.tfvars with your LabRole ARN"
	@echo ""
	cd infrastructure/terraform && \
	    terraform workspace select aws || terraform workspace new aws && \
		terraform init && \
		terraform apply -var-file="aws-learner-lab.tfvars" -auto-approve
	@echo ""
	@echo "=========================================="
	@echo "AWS deployment complete!"
	@echo "=========================================="
	@echo ""
	@echo "Set these environment variables:"
	@echo 'unset AWS_ENDPOINT_URL'
	@cd infrastructure/terraform && echo "export S3_BUCKET=$$(terraform output -raw s3_bucket_name)"
	@cd infrastructure/terraform && echo "export DYNAMODB_TABLE=$$(terraform output -raw dynamodb_table_name)"

# Destroy AWS resources
destroy-aws:
	@echo "Destroying AWS infrastructure..."
	cd infrastructure/terraform && \
	    terraform workspace select aws && \
		terraform destroy -var-file="aws-learner-lab.tfvars" -auto-approve
	@echo "AWS infrastructure destroyed"

#==============================================================================
# TESTING
#==============================================================================

# Upload a sample file to LocalStack for manual testing
test-upload-local:
	@echo "Uploading sample log file to LocalStack..."
	@cd infrastructure/terraform && terraform workspace select local > /dev/null
	@mkdir -p test/data
	@echo '{"timestamp": "2024-01-15T10:00:00Z", "level": "INFO", "endpoint": "/api/users", "response_time_ms": 45, "status_code": 200, "user_id": "user_1"}' > test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:01Z", "level": "ERROR", "endpoint": "/api/orders", "response_time_ms": 2500, "status_code": 500, "user_id": "user_2"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:02Z", "level": "WARN", "endpoint": "/api/products", "response_time_ms": 350, "status_code": 400, "user_id": "user_3"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:03Z", "level": "INFO", "endpoint": "/api/users", "response_time_ms": 89, "status_code": 200, "user_id": "user_4"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:04Z", "level": "DEBUG", "endpoint": "/health", "response_time_ms": 5, "status_code": 200, "user_id": "user_5"}' >> test/data/test_upload.json
	AWS_ENDPOINT_URL=http://localhost:4566 \
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=us-east-1 \
	aws s3 cp \
		test/data/test_upload.json \
		s3://$$(cd infrastructure/terraform && terraform output -raw s3_bucket_name)/logs/test_$$(date +%s)_upload.json
	@echo ""
	@echo "File uploaded! Waiting 5 seconds for processing..."
	@sleep 5
	@echo ""
	@make view-results-local

# Upload a sample file to AWS for manual testing
test-upload-aws:
	@echo "Uploading sample log file to AWS..."
	@cd infrastructure/terraform && terraform workspace select aws > /dev/null
	@mkdir -p test/data
	@echo '{"timestamp": "2024-01-15T10:00:00Z", "level": "INFO", "endpoint": "/api/users", "response_time_ms": 45, "status_code": 200, "user_id": "user_1"}' > test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:01Z", "level": "ERROR", "endpoint": "/api/orders", "response_time_ms": 2500, "status_code": 500, "user_id": "user_2"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:02Z", "level": "WARN", "endpoint": "/api/products", "response_time_ms": 350, "status_code": 400, "user_id": "user_3"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:03Z", "level": "INFO", "endpoint": "/api/users", "response_time_ms": 89, "status_code": 200, "user_id": "user_4"}' >> test/data/test_upload.json
	@echo '{"timestamp": "2024-01-15T10:00:04Z", "level": "DEBUG", "endpoint": "/health", "response_time_ms": 5, "status_code": 200, "user_id": "user_5"}' >> test/data/test_upload.json
	aws s3 cp \
		test/data/test_upload.json \
		s3://$$(cd infrastructure/terraform && terraform output -raw s3_bucket_name)/logs/test_$$(date +%s)_upload.json
	@echo ""
	@echo "File uploaded! Waiting 10 seconds for processing..."
	@sleep 10
	@echo ""
	@make view-results-aws

#==============================================================================
# VIEWING RESULTS
#==============================================================================

# View results in DynamoDB (LocalStack)
view-results-local:
	@echo "Results from DynamoDB (LocalStack):"
	@echo "=========================================="
	@cd infrastructure/terraform && terraform workspace select local > /dev/null
	$(eval DYNAMODB_TABLE := $(shell cd infrastructure/terraform && terraform output -raw dynamodb_table_name))
	@aws --endpoint-url=http://localhost:4566 dynamodb scan \
		--table-name $(DYNAMODB_TABLE) \
		--output table 2>/dev/null || echo "No results found or table doesn't exist"

# View results in DynamoDB (AWS)
view-results-aws:
	@echo "Results from DynamoDB (AWS):"
	@echo "=========================================="
	@cd infrastructure/terraform && terraform workspace select aws > /dev/null
	$(eval DYNAMODB_TABLE := $(shell cd infrastructure/terraform && terraform output -raw dynamodb_table_name))
	@aws dynamodb scan \
		--table-name $(DYNAMODB_TABLE) \
		--output table 2>/dev/null || echo "No results found or table doesn't exist"

#==============================================================================
# FULL WORKFLOWS
#==============================================================================

# Full local development cycle
full-local: localstack-up deploy-local run-tests-local
	@echo ""
	@echo "=========================================="
	@echo "Local development environment ready!"
	@echo "=========================================="

# Cleanup everything
clean-all: clean destroy-local localstack-down
	@echo "Cleaned up everything"

#==============================================================================
# ANALYSIS AND REPORTING
#==============================================================================

# Run systematic tests on LocalStack
run-tests-local:
	@echo "Running systematic tests on LocalStack..."
	@mkdir -p analysis/results/localstack
	cd infrastructure/terraform && terraform workspace select local
	AWS_ENDPOINT_URL=http://localhost:4566 \
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=us-east-1 \
	S3_BUCKET=$$(cd infrastructure/terraform && terraform output -raw s3_bucket_name) \
	DYNAMODB_TABLE=$$(cd infrastructure/terraform && terraform output -raw dynamodb_table_name) \
	python3 analysis/run_tests.py -e local -n 10 -s 100 500 1000 --concurrency 10

# Run systematic tests on AWS
run-tests-aws:
	@echo "Running systematic tests on AWS..."
	@mkdir -p analysis/results/aws
	cd infrastructure/terraform && terraform workspace select aws
	S3_BUCKET=$$(cd infrastructure/terraform && terraform output -raw s3_bucket_name) \
	DYNAMODB_TABLE=$$(cd infrastructure/terraform && terraform output -raw dynamodb_table_name) \
	python3 analysis/run_tests.py -e aws -n 10 -s 100 500 1000

# Generate charts from test results
generate-charts:
	@echo "Generating analysis charts..."
	@mkdir -p analysis/charts
	python3 analysis/generate_charts.py
	@echo ""
	@echo "Charts saved to analysis/charts/"
	@ls -la analysis/charts/*.png

# Run full analysis (both environments + charts)
full-analysis: run-tests-local run-tests-aws generate-charts
	@echo ""
	@echo "=========================================="
	@echo "Full analysis complete!"
	@echo "=========================================="
	@echo "Results: analysis/results/"
	@echo "Charts:  analysis/charts/"
	@echo "Report:  docs/report-template.md"

# Open charts directory (macOS)
open-charts:
	open analysis/charts/

#==============================================================================
# UTILITY
#==============================================================================

# Show current workspace
workspace-status:
	@echo "Current Terraform workspace:"
	@cd infrastructure/terraform && terraform workspace show
	@echo ""
	@echo "All workspaces:"
	@cd infrastructure/terraform && terraform workspace list
// cmd/worker/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/feature/dynamodb/attributevalue"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"event-pipeline/internal/metrics"
	"event-pipeline/internal/models"
	"event-pipeline/internal/processor"
)

var (
	s3Client         *s3.Client
	ddbClient        *dynamodb.Client
	metricsCollector *metrics.Collector
	tableName        string
)

func init() {
	ctx := context.Background()

	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		panic(fmt.Sprintf("failed to load config: %v", err))
	}

	// LocalStack support
	endpoint := os.Getenv("AWS_ENDPOINT_URL")

	if endpoint != "" {
		cfg.BaseEndpoint = aws.String(endpoint)
	}

	// Create S3 client with path-style addressing for LocalStack
	if endpoint != "" {
		s3Client = s3.NewFromConfig(cfg, func(o *s3.Options) {
			o.UsePathStyle = true  // CRITICAL: Forces path-style URLs
		})
	} else {
		s3Client = s3.NewFromConfig(cfg)
	}
	
	ddbClient = dynamodb.NewFromConfig(cfg)
	tableName = os.Getenv("DYNAMODB_TABLE")

	metricsCollector, err = metrics.NewCollector(ctx, "EventPipeline")
	if err != nil {
		fmt.Printf("Warning: failed to create metrics collector: %v\n", err)
	}
}

func handler(ctx context.Context, sqsEvent events.SQSEvent) error {
	for _, record := range sqsEvent.Records {
		if err := processMessage(ctx, record); err != nil {
			fmt.Printf("Error processing message: %v\n", err)
			// Return error to trigger retry/DLQ
			return err
		}
	}
	return nil
}

func processMessage(ctx context.Context, record events.SQSMessage) error {
	startTime := time.Now()

	// Parse job from SQS message
	var job models.ProcessingJob
	if err := json.Unmarshal([]byte(record.Body), &job); err != nil {
		return fmt.Errorf("failed to unmarshal job: %w", err)
	}

	fmt.Printf("Processing job %s: %s/%s\n", job.JobID, job.Bucket, job.Key)

	// Fetch file from S3
	getResp, err := s3Client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(job.Bucket),
		Key:    aws.String(job.Key),
	})
	if err != nil {
		return saveFailedResult(ctx, job, startTime, fmt.Errorf("failed to get S3 object: %w", err))
	}
	defer getResp.Body.Close()

	// Process the log file
	parser := processor.NewLogParser()
	aggregation, err := parser.Parse(getResp.Body)
	if err != nil {
		return saveFailedResult(ctx, job, startTime, fmt.Errorf("failed to parse logs: %w", err))
	}

	// Build result
	result := models.ProcessingResult{
		JobID:             job.JobID,
		Status:            "completed",
		LineCount:         aggregation.TotalLines,
		ErrorCount:        aggregation.ErrorCount,
		WarnCount:         aggregation.WarnCount,
		InfoCount:         aggregation.InfoCount,
		AvgResponseTimeMs: parser.GetAverageResponseTime(),
		MaxResponseTimeMs: aggregation.MaxResponseMs,
		UniqueUsers:       len(aggregation.UniqueUsers),
		UniqueEndpoints:   len(aggregation.UniqueEndpoints),
		ProcessingTimeMs:  time.Since(startTime).Milliseconds(),
		FileSizeBytes:     job.Size,
		StartedAt:         startTime,
		CompletedAt:       time.Now(),
		ExpiresAt:         time.Now().Add(7 * 24 * time.Hour).Unix(), // 7-day TTL
	}

	// Save to DynamoDB
	if err := saveResult(ctx, result); err != nil {
		return fmt.Errorf("failed to save result: %w", err)
	}

	// Emit metrics
	if metricsCollector != nil {
		metricsCollector.EmitBatch(ctx, map[string]metrics.MetricValue{
			"WorkerProcessingLatencyMs": metrics.LatencyMs(float64(result.ProcessingTimeMs)),
			"WorkerLinesProcessed":      metrics.Count(float64(result.LineCount)),
			"WorkerErrorsFound":         metrics.Count(float64(result.ErrorCount)),
			"WorkerSuccessCount":        metrics.Count(1),
		})
	}

	fmt.Printf("Completed job %s: %d lines in %dms\n", job.JobID, result.LineCount, result.ProcessingTimeMs)
	return nil
}

func saveResult(ctx context.Context, result models.ProcessingResult) error {
	item, err := attributevalue.MarshalMap(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	_, err = ddbClient.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: aws.String(tableName),
		Item:      item,
	})
	return err
}

func saveFailedResult(ctx context.Context, job models.ProcessingJob, startTime time.Time, processErr error) error {
	result := models.ProcessingResult{
		JobID:            job.JobID,
		Status:           "failed",
		ProcessingTimeMs: time.Since(startTime).Milliseconds(),
		FileSizeBytes:    job.Size,
		StartedAt:        startTime,
		CompletedAt:      time.Now(),
		ErrorMessage:     processErr.Error(),
		ExpiresAt:        time.Now().Add(7 * 24 * time.Hour).Unix(),
	}

	if err := saveResult(ctx, result); err != nil {
		fmt.Printf("Failed to save error result: %v\n", err)
	}

	if metricsCollector != nil {
		metricsCollector.EmitBatch(ctx, map[string]metrics.MetricValue{
			"WorkerFailureCount": metrics.Count(1),
		})
	}

	return processErr
}

func main() {
	lambda.Start(handler)
}
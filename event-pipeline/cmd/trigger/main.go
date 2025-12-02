// cmd/trigger/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/aws/aws-sdk-go-v2/service/sqs/types"

	"event-pipeline/internal/metrics"
	"event-pipeline/internal/models"
)

var (
	sqsClient        *sqs.Client
	s3Client         *s3.Client
	metricsCollector *metrics.Collector
	queueURL         string
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

	sqsClient = sqs.NewFromConfig(cfg)
	
    // Create S3 client with path-style addressing for LocalStack
	if endpoint != "" {
		s3Client = s3.NewFromConfig(cfg, func(o *s3.Options) {
			o.UsePathStyle = true  // CRITICAL: Forces path-style URLs
		})
	} else {
		s3Client = s3.NewFromConfig(cfg)
	}

	queueURL = os.Getenv("QUEUE_URL")

	metricsCollector, err = metrics.NewCollector(ctx, "EventPipeline")
	if err != nil {
		fmt.Printf("Warning: failed to create metrics collector: %v\n", err)
	}
}

func handler(ctx context.Context, s3Event events.S3Event) error {
	for _, record := range s3Event.Records {
		if err := processRecord(ctx, record); err != nil {
			fmt.Printf("Error processing record: %v\n", err)
			if metricsCollector != nil {
				metricsCollector.EmitBatch(ctx, map[string]metrics.MetricValue{
					"TriggerFailures": metrics.Count(1),
				})
			}
			// Continue processing other records instead of failing the whole batch.
			continue
		}
	}
	return nil
}

func processRecord(ctx context.Context, record events.S3EventRecord) error {
	startTime := time.Now()

	bucket := record.S3.Bucket.Name
	key := record.S3.Object.Key

	// Skip non-JSON files
	if !strings.HasSuffix(strings.ToLower(key), ".json") {
		fmt.Printf("Skipping non-JSON file: %s\n", key)
		return nil
	}

	// Get object metadata
	headResp, err := s3Client.HeadObject(ctx, &s3.HeadObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})
	if err != nil {
		return fmt.Errorf("failed to head object %s/%s: %w", bucket, key, err)
	}

	// Extract the test_id from the S3 key if it follows the pattern
	// "logs/test_{test_id}_{timestamp}.json"
	var jobID string
	parts := strings.Split(key, "_")
	if len(parts) >= 3 && parts[0] == "logs/test" {
		jobID = parts[1]
		fmt.Printf("Extracted test_id '%s' from key\n", jobID)
	} else {
		return fmt.Errorf("could not extract test_id from key: %s", key)
	}

	// Create processing job
	job := models.ProcessingJob{
		JobID:       jobID,
		Bucket:      bucket,
		Key:         key,
		Size:        *headResp.ContentLength,
		ContentType: aws.ToString(headResp.ContentType),
		ReceivedAt:  record.EventTime,
		ValidatedAt: time.Now(),
	}

	// Serialize and send to SQS
	jobBytes, err := json.Marshal(job)
	if err != nil {
		return fmt.Errorf("failed to marshal job: %w", err)
	}

	_, err = sqsClient.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:    aws.String(queueURL),
		MessageBody: aws.String(string(jobBytes)),
		MessageAttributes: map[string]types.MessageAttributeValue{
			"JobID": {
				DataType:    aws.String("String"),
				StringValue: aws.String(job.JobID),
			},
		},
	})
	if err != nil {
		return fmt.Errorf("failed to send SQS message: %w", err)
	}

	// Emit metrics
	validationLatency := float64(time.Since(startTime).Milliseconds())
	if metricsCollector != nil {
		metricsCollector.EmitBatch(ctx, map[string]metrics.MetricValue{
			"TriggerValidationLatencyMs": metrics.LatencyMs(validationLatency),
			"TriggerFileSizeBytes":       metrics.MetricValue{Value: float64(job.Size), Unit: "Bytes"},
			"TriggerInvocations":         metrics.Count(1),
		})
	}

	fmt.Printf("Queued job %s for file %s/%s (%.2fms)\n", job.JobID, bucket, key, validationLatency)
	return nil
}

func main() {
	lambda.Start(handler)
}
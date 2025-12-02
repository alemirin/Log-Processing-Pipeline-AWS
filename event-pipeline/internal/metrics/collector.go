// internal/metrics/collector.go
package metrics

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/cloudwatch"
	"github.com/aws/aws-sdk-go-v2/service/cloudwatch/types"
)

// Collector handles custom CloudWatch metrics emission
type Collector struct {
	client    *cloudwatch.Client
	namespace string
	dims      []types.Dimension
}

// NewCollector creates a new metrics collector
func NewCollector(ctx context.Context, namespace string) (*Collector, error) {
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load AWS config: %w", err)
	}

	// Check for LocalStack endpoint
	if endpoint := os.Getenv("AWS_ENDPOINT_URL"); endpoint != "" {
		cfg.BaseEndpoint = aws.String(endpoint)
	}

	client := cloudwatch.NewFromConfig(cfg)

	// Default dimensions
	dims := []types.Dimension{
		{
			Name:  aws.String("Environment"),
			Value: aws.String(getEnvironment()),
		},
		{
			Name:  aws.String("Service"),
			Value: aws.String("event-pipeline"),
		},
	}

	return &Collector{
		client:    client,
		namespace: namespace,
		dims:      dims,
	}, nil
}

// EmitLatency records a latency metric in milliseconds
func (c *Collector) EmitLatency(ctx context.Context, name string, valueMs float64) error {
	return c.emit(ctx, name, valueMs, types.StandardUnitMilliseconds)
}

// EmitCount records a count metric
func (c *Collector) EmitCount(ctx context.Context, name string, value float64) error {
	return c.emit(ctx, name, value, types.StandardUnitCount)
}

// EmitBytes records a bytes metric
func (c *Collector) EmitBytes(ctx context.Context, name string, value float64) error {
	return c.emit(ctx, name, value, types.StandardUnitBytes)
}

// emit sends a metric to CloudWatch
func (c *Collector) emit(ctx context.Context, name string, value float64, unit types.StandardUnit) error {
	_, err := c.client.PutMetricData(ctx, &cloudwatch.PutMetricDataInput{
		Namespace: aws.String(c.namespace),
		MetricData: []types.MetricDatum{
			{
				MetricName: aws.String(name),
				Value:      aws.Float64(value),
				Unit:       unit,
				Timestamp:  aws.Time(time.Now()),
				Dimensions: c.dims,
			},
		},
	})

	if err != nil {
		return fmt.Errorf("failed to emit metric %s: %w", name, err)
	}
	return nil
}

// EmitBatch sends multiple metrics at once (more efficient)
func (c *Collector) EmitBatch(ctx context.Context, metrics map[string]MetricValue) error {
	if len(metrics) == 0 {
		return nil
	}

	data := make([]types.MetricDatum, 0, len(metrics))
	timestamp := aws.Time(time.Now())

	for name, mv := range metrics {
		data = append(data, types.MetricDatum{
			MetricName: aws.String(name),
			Value:      aws.Float64(mv.Value),
			Unit:       mv.Unit,
			Timestamp:  timestamp,
			Dimensions: c.dims,
		})
	}

	// CloudWatch accepts max 1000 metrics per call, batch if needed
	for i := 0; i < len(data); i += 1000 {
		end := i + 1000
		if end > len(data) {
			end = len(data)
		}

		_, err := c.client.PutMetricData(ctx, &cloudwatch.PutMetricDataInput{
			Namespace:  aws.String(c.namespace),
			MetricData: data[i:end],
		})
		if err != nil {
			return fmt.Errorf("failed to emit batch metrics: %w", err)
		}
	}

	return nil
}

// MetricValue holds a metric value and its unit
type MetricValue struct {
	Value float64
	Unit  types.StandardUnit
}

// Helper to create latency metric value
func LatencyMs(v float64) MetricValue {
	return MetricValue{Value: v, Unit: types.StandardUnitMilliseconds}
}

// Helper to create count metric value
func Count(v float64) MetricValue {
	return MetricValue{Value: v, Unit: types.StandardUnitCount}
}

// getEnvironment returns the current environment
func getEnvironment() string {
	if env := os.Getenv("ENVIRONMENT"); env != "" {
		return env
	}
	return "development"
}
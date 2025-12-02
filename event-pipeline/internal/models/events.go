// internal/models/events.go
package models

import "time"

// ProcessingJob represents a job queued for processing
type ProcessingJob struct {
	JobID       string    `json:"job_id" dynamodbav:"job_id"`
	Bucket      string    `json:"bucket" dynamodbav:"bucket"`
	Key         string    `json:"key" dynamodbav:"key"`
	Size        int64     `json:"size" dynamodbav:"size"`
	ContentType string    `json:"content_type" dynamodbav:"content_type"`
	ReceivedAt  time.Time `json:"received_at" dynamodbav:"received_at"`
	ValidatedAt time.Time `json:"validated_at" dynamodbav:"validated_at"`
}

// ProcessingResult represents the outcome of processing a job
type ProcessingResult struct {
	JobID            string    `json:"job_id" dynamodbav:"job_id"`
	Status           string    `json:"status" dynamodbav:"status"` // "completed", "failed"
	LineCount        int       `json:"line_count,omitempty" dynamodbav:"line_count,omitempty"`
	ErrorCount       int       `json:"error_count,omitempty" dynamodbav:"error_count,omitempty"`
	WarnCount        int       `json:"warn_count,omitempty" dynamodbav:"warn_count,omitempty"`
	InfoCount        int       `json:"info_count,omitempty" dynamodbav:"info_count,omitempty"`
	AvgResponseTimeMs float64  `json:"avg_response_time_ms,omitempty" dynamodbav:"avg_response_time_ms,omitempty"`
	MaxResponseTimeMs int      `json:"max_response_time_ms,omitempty" dynamodbav:"max_response_time_ms,omitempty"`
	UniqueUsers      int       `json:"unique_users,omitempty" dynamodbav:"unique_users,omitempty"`
	UniqueEndpoints  int       `json:"unique_endpoints,omitempty" dynamodbav:"unique_endpoints,omitempty"`
	ProcessingTimeMs int64     `json:"processing_time_ms" dynamodbav:"processing_time_ms"`
	FileSizeBytes    int64     `json:"file_size_bytes" dynamodbav:"file_size_bytes"`
	StartedAt        time.Time `json:"started_at" dynamodbav:"started_at"`
	CompletedAt      time.Time `json:"completed_at" dynamodbav:"completed_at"`
	ErrorMessage     string    `json:"error_message,omitempty" dynamodbav:"error_message,omitempty"`
	ExpiresAt        int64     `json:"expires_at" dynamodbav:"expires_at"` // TTL
}

// LogEntry represents a single log line from the input file
type LogEntry struct {
	Timestamp      string `json:"timestamp"`
	Level          string `json:"level"`
	Endpoint       string `json:"endpoint"`
	ResponseTimeMs int    `json:"response_time_ms"`
	StatusCode     int    `json:"status_code"`
	UserID         string `json:"user_id"`
	Message        string `json:"message,omitempty"`
}

// LogAggregation holds aggregated statistics from log processing
type LogAggregation struct {
	TotalLines       int
	ProcessedLines   int
	ErrorCount       int
	WarnCount        int
	InfoCount        int
	DebugCount       int
	TotalResponseMs  int64
	MaxResponseMs    int
	UniqueUsers      map[string]struct{}
	UniqueEndpoints  map[string]struct{}
	StatusCodeCounts map[int]int
}

// NewLogAggregation creates an initialized LogAggregation
func NewLogAggregation() *LogAggregation {
	return &LogAggregation{
		UniqueUsers:      make(map[string]struct{}),
		UniqueEndpoints:  make(map[string]struct{}),
		StatusCodeCounts: make(map[int]int),
	}
}
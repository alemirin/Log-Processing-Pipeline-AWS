// internal/processor/logparser.go
package processor

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"

	"event-pipeline/internal/models"
)

// LogParser processes log files and extracts statistics
type LogParser struct {
	aggregation *models.LogAggregation
}

// NewLogParser creates a new LogParser instance
func NewLogParser() *LogParser {
	return &LogParser{
		aggregation: models.NewLogAggregation(),
	}
}

// Parse reads a log file and aggregates statistics
func (p *LogParser) Parse(reader io.Reader) (*models.LogAggregation, error) {
	scanner := bufio.NewScanner(reader)
	
	// Increase buffer size for potentially long lines
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	lineNum := 0
	for scanner.Scan() {
		lineNum++
		line := scanner.Bytes()
		
		if len(line) == 0 {
			continue
		}

		var entry models.LogEntry
		if err := json.Unmarshal(line, &entry); err != nil {
			// Count parse errors as warnings, continue processing
			p.aggregation.WarnCount++
			continue
		}

		p.processEntry(&entry)
		p.aggregation.ProcessedLines++
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error scanning file: %w", err)
	}

	p.aggregation.TotalLines = lineNum
	return p.aggregation, nil
}

// processEntry updates aggregation with a single log entry
func (p *LogParser) processEntry(entry *models.LogEntry) {
	// Count by log level
	switch entry.Level {
	case "ERROR":
		p.aggregation.ErrorCount++
	case "WARN":
		p.aggregation.WarnCount++
	case "INFO":
		p.aggregation.InfoCount++
	case "DEBUG":
		p.aggregation.DebugCount++
	}

	// Track response times
	p.aggregation.TotalResponseMs += int64(entry.ResponseTimeMs)
	if entry.ResponseTimeMs > p.aggregation.MaxResponseMs {
		p.aggregation.MaxResponseMs = entry.ResponseTimeMs
	}

	// Track unique users
	if entry.UserID != "" {
		p.aggregation.UniqueUsers[entry.UserID] = struct{}{}
	}

	// Track unique endpoints
	if entry.Endpoint != "" {
		p.aggregation.UniqueEndpoints[entry.Endpoint] = struct{}{}
	}

	// Track status codes
	if entry.StatusCode > 0 {
		p.aggregation.StatusCodeCounts[entry.StatusCode]++
	}
}

// GetAverageResponseTime calculates average response time
func (p *LogParser) GetAverageResponseTime() float64 {
	// Use ProcessedLines for an accurate average, as some lines might be skipped.
	if p.aggregation.ProcessedLines == 0 {
		return 0
	}
	return float64(p.aggregation.TotalResponseMs) / float64(p.aggregation.ProcessedLines)
}

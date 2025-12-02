#!/usr/bin/env python3
"""
Systematic test runner for Event Pipeline
Collects metrics from LocalStack and AWS deployments
"""

import boto3
import json
import time
import os
import csv
import random
import string
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from botocore.config import Config

@dataclass
class TestResult:
    """Single test result"""
    test_id: str
    environment: str
    timestamp: str
    file_size_bytes: int
    line_count: int
    upload_time_ms: float
    end_to_end_time_ms: float
    processing_time_ms: Optional[float]
    status: str
    error_message: Optional[str]
    cold_start: bool

@dataclass 
class TestSummary:
    """Summary statistics for a test run"""
    environment: str
    total_tests: int
    successful_tests: int
    failed_tests: int
    avg_upload_time_ms: float
    avg_e2e_time_ms: float
    avg_processing_time_ms: float
    p50_e2e_ms: float
    p95_e2e_ms: float
    p99_e2e_ms: float
    min_e2e_ms: float
    max_e2e_ms: float
    throughput_files_per_sec: float
    error_rate_percent: float
    cold_start_count: int


class PipelineTester:
    def __init__(self, environment: str):
        self.environment = environment
        self.results: List[TestResult] = []
        
        # Configure AWS clients
        if environment == "local":
            endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
            self.s3 = boto3.client('s3', 
                endpoint_url=endpoint_url,
                aws_access_key_id='test',
                aws_secret_access_key='test',
                region_name='us-east-1',
                config=Config(s3={'addressing_style': 'path'})
            )
            self.dynamodb = boto3.client('dynamodb',
                endpoint_url=endpoint_url,
                aws_access_key_id='test',
                aws_secret_access_key='test',
                region_name='us-east-1'
            )
        else:
            self.s3 = boto3.client('s3')
            self.dynamodb = boto3.client('dynamodb')
        
        self.bucket = os.getenv("S3_BUCKET")
        self.table = os.getenv("DYNAMODB_TABLE")
        
        if not self.bucket or not self.table:
            raise ValueError("S3_BUCKET and DYNAMODB_TABLE environment variables required")
    
    def generate_log_data(self, num_lines: int) -> str:
        """Generate sample log data"""
        levels = ["INFO", "WARN", "ERROR", "DEBUG"]
        weights = [70, 15, 10, 5]
        endpoints = ["/api/users", "/api/orders", "/api/products", "/health"]
        
        lines = []
        for i in range(num_lines):
            level = random.choices(levels, weights=weights)[0]
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": level,
                "endpoint": random.choice(endpoints),
                "response_time_ms": random.randint(5, 500) if level != "ERROR" else random.randint(500, 5000),
                "status_code": 200 if level in ["INFO", "DEBUG"] else (400 if level == "WARN" else 500),
                "user_id": f"user_{random.randint(1, 100)}"
            }
            lines.append(json.dumps(entry))
        
        return "\n".join(lines)
    
    def upload_file(self, data: str, key: str) -> float:
        """Upload file to S3 and return upload time in ms"""
        start = time.time()
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data.encode('utf-8'),
            ContentType='application/json'
        )
        return (time.time() - start) * 1000
    
    def wait_for_result(self, test_id: str, timeout: int = 180) -> Optional[dict]:
        """Poll DynamoDB for processing result"""
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                response = self.dynamodb.get_item(
                    TableName=self.table,
                    Key={'job_id': {'S': test_id}}
                )
                
                if 'Item' in response:
                    return self._parse_dynamodb_item(response['Item'])
                
            except Exception as e:
                print(f"  Error polling DynamoDB: {e}")
            
            time.sleep(0.25) # Poll more frequently
        
        return None
    
    def _parse_dynamodb_item(self, item: dict) -> dict:
        """Parse DynamoDB item to regular dict"""
        result = {}
        for key, value in item.items():
            if 'S' in value:
                result[key] = value['S']
            elif 'N' in value:
                result[key] = float(value['N'])
            elif 'BOOL' in value:
                result[key] = value['BOOL']
        return result
    
    def clear_results_table(self):
        """Clear previous results from DynamoDB"""
        try:
            # Scan for keys to delete
            scan_paginator = self.dynamodb.get_paginator('scan')
            pages = scan_paginator.paginate(TableName=self.table, ProjectionExpression='job_id')
            
            delete_requests = []
            for page in pages:
                for item in page.get('Items', []):
                    delete_requests.append({'DeleteRequest': {'Key': {'job_id': item['job_id']}}})

            # Batch delete items (25 at a time is the limit)
            if delete_requests:
                for i in range(0, len(delete_requests), 25):
                    chunk = delete_requests[i:i + 25]
                    self.dynamodb.batch_write_item(RequestItems={self.table: chunk})
        except Exception as e:
            print(f"Warning: Could not clear results table '{self.table}': {e}")
    
    def run_single_test(self, test_num: int, line_count: int, is_cold_start: bool = False) -> TestResult:
        """Run a single test iteration"""
        test_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        timestamp = datetime.utcnow().isoformat()
        key = f"logs/test_{test_id}_{int(time.time())}.json"
        
        print(f"  Test {test_num}: Generating {line_count} lines...")
        data = self.generate_log_data(line_count)
        file_size = len(data.encode('utf-8'))
        
        print(f"  Test {test_num}: Uploading to s3://{self.bucket}/{key}")
        e2e_start = time.time()
        upload_time = self.upload_file(data, key)
        
        print(f"  Test {test_num}: Waiting for processing result...")
        result = self.wait_for_result(test_id, timeout=180)
        e2e_time = (time.time() - e2e_start) * 1000
        
        if result:
            return TestResult(
                test_id=test_id,
                environment=self.environment,
                timestamp=timestamp,
                file_size_bytes=file_size,
                line_count=line_count,
                upload_time_ms=upload_time,
                end_to_end_time_ms=e2e_time,
                processing_time_ms=result.get('processing_time_ms'),
                status="success",
                error_message=None,
                cold_start=is_cold_start
            )
        else:
            return TestResult(
                test_id=test_id,
                environment=self.environment,
                timestamp=timestamp,
                file_size_bytes=file_size,
                line_count=line_count,
                upload_time_ms=upload_time,
                end_to_end_time_ms=e2e_time,
                processing_time_ms=None,
                status="timeout",
                error_message="No result received within timeout",
                cold_start=is_cold_start
            )
    
    def run_test_suite(self, 
                       num_tests: int = 20,
                       line_counts: List[int] = [100, 500, 1000],
                       warmup_runs: int = 2,
                       concurrency: int = 10) -> List[TestResult]:
        """Run complete test suite"""
        print(f"\n{'='*60}")
        print(f"Running test suite on {self.environment.upper()}")
        print(f"{'='*60}")
        print(f"Tests per size: {num_tests}")
        print(f"Line counts: {line_counts}")
        print(f"Warmup runs: {warmup_runs}")
        print(f"Concurrency level: {concurrency}")
        print()
        
        all_results = []
        
        # Clear the table once before starting
        print("Clearing previous results from DynamoDB table...")
        self.clear_results_table()
        
        # Warmup runs (cold starts)
        print("Running warmup (cold start) tests...")
        for i in range(warmup_runs):
            result = self.run_single_test(i + 1, line_counts[0], is_cold_start=True)
            all_results.append(result)
            print(f"  Warmup {i+1}: {result.status} - E2E: {result.end_to_end_time_ms:.0f}ms")
            time.sleep(1) # Give some time between warmups
        
        # Main test runs
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for line_count in line_counts:
                print(f"\nSubmitting {num_tests} tests for file size with {line_count} lines...")
                
                futures = {executor.submit(self.run_single_test, i + 1, line_count): i 
                           for i in range(num_tests)}
                
                test_count = 0
                for future in as_completed(futures):
                    test_count += 1
                    try:
                        result = future.result()
                        all_results.append(result)
                        status_icon = "✓" if result.status == "success" else "✗"
                        print(f"  [{status_icon}] Completed test {test_count}/{num_tests} (size {line_count}): "
                              f"E2E={result.end_to_end_time_ms:.0f}ms, "
                              f"Processing={result.processing_time_ms or 'N/A'}ms")
                    except Exception as exc:
                        print(f"  [✗] A test generated an exception: {exc}")
        
        self.results = all_results
        return all_results
    
    def calculate_summary(self) -> TestSummary:
        """Calculate summary statistics"""
        import numpy as np
        
        successful = [r for r in self.results if r.status == "success" and not r.cold_start]
        
        if not successful:
            raise ValueError("No successful test results to summarize")
        
        e2e_times = [r.end_to_end_time_ms for r in successful]
        upload_times = [r.upload_time_ms for r in successful]
        processing_times = [r.processing_time_ms for r in successful if r.processing_time_ms]
        
        total_time_sec = sum(e2e_times) / 1000
        
        return TestSummary(
            environment=self.environment,
            total_tests=len(self.results),
            successful_tests=len(successful),
            failed_tests=len([r for r in self.results if r.status != "success"]),
            avg_upload_time_ms=np.mean(upload_times),
            avg_e2e_time_ms=np.mean(e2e_times),
            avg_processing_time_ms=np.mean(processing_times) if processing_times else 0,
            p50_e2e_ms=np.percentile(e2e_times, 50),
            p95_e2e_ms=np.percentile(e2e_times, 95),
            p99_e2e_ms=np.percentile(e2e_times, 99),
            min_e2e_ms=min(e2e_times),
            max_e2e_ms=max(e2e_times),
            throughput_files_per_sec=len(successful) / total_time_sec if total_time_sec > 0 else 0,
            error_rate_percent=(len(self.results) - len(successful)) / len(self.results) * 100,
            cold_start_count=len([r for r in self.results if r.cold_start])
        )
    
    def save_results(self, output_dir: str):
        """Save results to CSV and JSON"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results as CSV
        csv_path = os.path.join(output_dir, f"results_{self.environment}_{timestamp}.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
            writer.writeheader()
            for result in self.results:
                writer.writerow(asdict(result))
        print(f"Saved detailed results to {csv_path}")
        
        # Save summary as JSON
        summary = self.calculate_summary()
        json_path = os.path.join(output_dir, f"summary_{self.environment}_{timestamp}.json")
        with open(json_path, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"Saved summary to {json_path}")
        
        # Also save a "latest" version for easy access
        latest_csv = os.path.join(output_dir, f"results_{self.environment}_latest.csv")
        latest_json = os.path.join(output_dir, f"summary_{self.environment}_latest.json")
        
        with open(latest_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
            writer.writeheader()
            for result in self.results:
                writer.writerow(asdict(result))
        
        with open(latest_json, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        
        return csv_path, json_path


def print_summary_table(summary: TestSummary):
    """Print a formatted summary table"""
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY - {summary.environment.upper()}")
    print(f"{'='*60}")
    print(f"Total Tests:        {summary.total_tests}")
    print(f"Successful:         {summary.successful_tests}")
    print(f"Failed:             {summary.failed_tests}")
    print(f"Error Rate:         {summary.error_rate_percent:.1f}%")
    print(f"Cold Starts:        {summary.cold_start_count}")
    print()
    print("Latency (End-to-End):")
    print(f"  Average:          {summary.avg_e2e_time_ms:.0f} ms")
    print(f"  P50:              {summary.p50_e2e_ms:.0f} ms")
    print(f"  P95:              {summary.p95_e2e_ms:.0f} ms")
    print(f"  P99:              {summary.p99_e2e_ms:.0f} ms")
    print(f"  Min:              {summary.min_e2e_ms:.0f} ms")
    print(f"  Max:              {summary.max_e2e_ms:.0f} ms")
    print()
    print(f"Avg Upload Time:    {summary.avg_upload_time_ms:.0f} ms")
    print(f"Avg Processing:     {summary.avg_processing_time_ms:.0f} ms")
    print(f"Throughput:         {summary.throughput_files_per_sec:.2f} files/sec")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Run pipeline tests')
    parser.add_argument('--environment', '-e', choices=['local', 'aws'], required=True,
                        help='Test environment (local or aws)')
    parser.add_argument('--tests', '-n', type=int, default=10,
                        help='Number of tests per file size (default: 10)')
    parser.add_argument('--sizes', '-s', type=int, nargs='+', default=[100, 500, 1000],
                        help='Line counts to test (default: 100 500 1000)')
    parser.add_argument('--output', '-o', type=str, default='analysis/results',
                        help='Output directory for results')
    parser.add_argument('--warmup', '-w', type=int, default=2,
                        help='Number of warmup runs (default: 2)')
    parser.add_argument('--concurrency', '-c', type=int, default=10,
                        help='Number of tests to run in parallel (default: 10)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = os.path.join(args.output, args.environment)
    
    # Run tests
    tester = PipelineTester(args.environment)
    results = tester.run_test_suite(
        num_tests=args.tests,
        line_counts=args.sizes,
        warmup_runs=args.warmup,
        concurrency=args.concurrency
    )
    
    # Calculate and print summary
    summary = tester.calculate_summary()
    print_summary_table(summary)
    
    # Save results
    tester.save_results(output_dir)
    
    print(f"\nResults saved to {output_dir}/")
    print("Run 'python analysis/generate_charts.py' to generate visualizations")


if __name__ == "__main__":
    main()
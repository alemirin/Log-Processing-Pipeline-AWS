#!/usr/bin/env python3
"""
Chart generator for Event Pipeline analysis
Creates visualizations comparing LocalStack vs AWS performance
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import os
import argparse
from pathlib import Path

# Set style for professional-looking charts
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Custom colors for consistency
COLORS = {
    'localstack': '#FF6B6B',  # Coral red
    'aws': '#4ECDC4',          # Teal
    'highlight': '#FFE66D'     # Yellow
}


def load_results(results_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Load test results from CSV and JSON files"""
    
    local_csv = Path(results_dir) / "local" / "results_local_latest.csv"
    aws_csv = Path(results_dir) / "aws" / "results_aws_latest.csv"
    local_json = Path(results_dir) / "local" / "summary_local_latest.json"
    aws_json = Path(results_dir) / "aws" / "summary_aws_latest.json"
    
    # Load CSVs
    df_local = pd.read_csv(local_csv) if local_csv.exists() else pd.DataFrame()
    df_aws = pd.read_csv(aws_csv) if aws_csv.exists() else pd.DataFrame()
    
    # Load summaries
    with open(local_json) as f:
        summary_local = json.load(f) if local_json.exists() else {}
    with open(aws_json) as f:
        summary_aws = json.load(f) if aws_json.exists() else {}
    
    return df_local, df_aws, summary_local, summary_aws


def create_latency_comparison_chart(df_local: pd.DataFrame, df_aws: pd.DataFrame, output_dir: str):
    """Create box plot comparing latency distributions"""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Prepare data
    df_local_success = df_local[df_local['status'] == 'success'].copy()
    df_aws_success = df_aws[df_aws['status'] == 'success'].copy()
    
    df_local_success['Environment'] = 'LocalStack'
    df_aws_success['Environment'] = 'AWS'
    
    combined = pd.concat([df_local_success, df_aws_success])
    
    # Create box plot
    sns.boxplot(
        data=combined, 
        x='Environment', 
        y='end_to_end_time_ms',
        palette=[COLORS['localstack'], COLORS['aws']],
        ax=ax
    )
    
    ax.set_ylabel('End-to-End Latency (ms)', fontsize=12)
    ax.set_xlabel('Environment', fontsize=12)
    ax.set_title('End-to-End Latency Distribution: LocalStack vs AWS', fontsize=14, fontweight='bold')
    
    # Add median labels
    medians = combined.groupby('Environment')['end_to_end_time_ms'].median()
    for i, env in enumerate(['LocalStack', 'AWS']):
        if env in medians.index:
            ax.annotate(f'Median: {medians[env]:.0f}ms', 
                       xy=(i, medians[env]), 
                       xytext=(10, 10),
                       textcoords='offset points',
                       fontsize=10,
                       fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'latency_comparison.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: latency_comparison.png")


def create_percentile_chart(summary_local: dict, summary_aws: dict, output_dir: str):
    """Create bar chart comparing percentile latencies"""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    percentiles = ['P50', 'P95', 'P99']
    local_values = [
        summary_local.get('p50_e2e_ms', 0),
        summary_local.get('p95_e2e_ms', 0),
        summary_local.get('p99_e2e_ms', 0)
    ]
    aws_values = [
        summary_aws.get('p50_e2e_ms', 0),
        summary_aws.get('p95_e2e_ms', 0),
        summary_aws.get('p99_e2e_ms', 0)
    ]
    
    x = np.arange(len(percentiles))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, local_values, width, label='LocalStack', color=COLORS['localstack'])
    bars2 = ax.bar(x + width/2, aws_values, width, label='AWS', color=COLORS['aws'])
    
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_xlabel('Percentile', fontsize=12)
    ax.set_title('Latency Percentiles: LocalStack vs AWS', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(percentiles)
    ax.legend()
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.0f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'percentile_comparison.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: percentile_comparison.png")


def create_throughput_chart(summary_local: dict, summary_aws: dict, output_dir: str):
    """Create bar chart comparing throughput and error rates"""
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Throughput comparison
    ax1 = axes[0]
    environments = ['LocalStack', 'AWS']
    throughputs = [
        summary_local.get('throughput_files_per_sec', 0),
        summary_aws.get('throughput_files_per_sec', 0)
    ]
    
    bars = ax1.bar(environments, throughputs, color=[COLORS['localstack'], COLORS['aws']])
    ax1.set_ylabel('Files per Second', fontsize=12)
    ax1.set_title('Throughput Comparison', fontsize=14, fontweight='bold')
    
    for bar, val in zip(bars, throughputs):
        ax1.annotate(f'{val:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=11, fontweight='bold')
    
    # Error rate comparison
    ax2 = axes[1]
    error_rates = [
        (summary_local.get('failed_tests', 0) / summary_local.get('total_tests', 1)) * 100,
        (summary_aws.get('failed_tests', 0) / summary_aws.get('total_tests', 1)) * 100
    ]
    
    bars = ax2.bar(environments, error_rates, color=[COLORS['localstack'], COLORS['aws']])
    ax2.set_ylabel('Error Rate (%)', fontsize=12)
    ax2.set_title('Error Rate Comparison', fontsize=14, fontweight='bold')
    # Set a fixed y-limit for error rate, e.g., 0-10% or adjust as needed
    ax2.set_ylim(0, max(max(error_rates), 5) * 1.2)
    
    for bar, val in zip(bars, error_rates):
        ax2.annotate(f'{val:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'throughput_error_comparison.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: throughput_error_comparison.png")


def create_latency_by_file_size(df_local: pd.DataFrame, df_aws: pd.DataFrame, output_dir: str):
    """Create line chart showing latency vs file size"""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Group by line count and calculate mean
    df_local_success = df_local[df_local['status'] == 'success']
    df_aws_success = df_aws[df_aws['status'] == 'success']
    
    local_by_size = df_local_success.groupby('line_count')['end_to_end_time_ms'].agg(['mean', 'std']).reset_index()
    aws_by_size = df_aws_success.groupby('line_count')['end_to_end_time_ms'].agg(['mean', 'std']).reset_index()
    
    # Plot with error bars
    ax.errorbar(local_by_size['line_count'], local_by_size['mean'], 
                yerr=local_by_size['std'], marker='o', markersize=8,
                label='LocalStack', color=COLORS['localstack'], capsize=5, linewidth=2)
    ax.errorbar(aws_by_size['line_count'], aws_by_size['mean'],
                yerr=aws_by_size['std'], marker='s', markersize=8,
                label='AWS', color=COLORS['aws'], capsize=5, linewidth=2)
    
    ax.set_xlabel('Log Lines per File', fontsize=12)
    ax.set_ylabel('End-to-End Latency (ms)', fontsize=12)
    ax.set_title('Latency vs File Size', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'latency_by_filesize.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: latency_by_filesize.png")


def create_latency_timeline(df_local: pd.DataFrame, df_aws: pd.DataFrame, output_dir: str):
    """Create scatter plot showing latency over time (detect cold starts)"""
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    for ax, (df, name, color) in zip(axes, 
        [(df_local, 'LocalStack', COLORS['localstack']), 
         (df_aws, 'AWS', COLORS['aws'])]):
        
        df_success = df[df['status'] == 'success'].copy()
        df_success['test_number'] = range(len(df_success))
        
        # Color cold starts differently
        cold_starts = df_success[df_success['cold_start'] == True]
        warm_starts = df_success[df_success['cold_start'] == False]
        
        ax.scatter(warm_starts['test_number'], warm_starts['end_to_end_time_ms'],
                   alpha=0.7, color=color, label='Warm', s=50)
        ax.scatter(cold_starts['test_number'], cold_starts['end_to_end_time_ms'],
                   alpha=0.9, color=COLORS['highlight'], label='Cold Start', 
                   s=100, marker='^', edgecolors='black')
        
        ax.set_xlabel('Test Number', fontsize=12)
        ax.set_ylabel('End-to-End Latency (ms)', fontsize=12)
        ax.set_title(f'{name}: Latency Over Time', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'latency_timeline.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: latency_timeline.png")


def create_component_breakdown(df_local: pd.DataFrame, df_aws: pd.DataFrame, output_dir: str):
    """Create stacked bar chart showing latency breakdown by component"""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Calculate component times (approximation based on available data)
    def calc_components(df):
        df_success = df[df['status'] == 'success']
        upload_time = df_success['upload_time_ms'].mean()
        processing_time = df_success['processing_time_ms'].mean()
        # Queue + overhead time is the remainder
        e2e_time = df_success['end_to_end_time_ms'].mean()
        queue_overhead = max(0, e2e_time - upload_time - processing_time)
        return upload_time, processing_time, queue_overhead
    
    local_upload, local_proc, local_queue = calc_components(df_local)
    aws_upload, aws_proc, aws_queue = calc_components(df_aws)
    
    environments = ['LocalStack', 'AWS']
    upload_times = [local_upload, aws_upload]
    processing_times = [local_proc, aws_proc]
    queue_times = [local_queue, aws_queue]
    
    x = np.arange(len(environments))
    width = 0.5
    
    bars1 = ax.bar(x, upload_times, width, label='S3 Upload', color='#3498db')
    bars2 = ax.bar(x, processing_times, width, bottom=upload_times, label='Lambda Processing', color='#2ecc71')
    bars3 = ax.bar(x, queue_times, width, bottom=np.array(upload_times) + np.array(processing_times),
                   label='SQS + Overhead', color='#e74c3c')
    
    ax.set_ylabel('Time (ms)', fontsize=12)
    ax.set_xlabel('Environment', fontsize=12)
    ax.set_title('Latency Breakdown by Component', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(environments)
    ax.legend(loc='upper right')
    
    # Add total labels
    totals = [local_upload + local_proc + local_queue, aws_upload + aws_proc + aws_queue]
    for i, total in enumerate(totals):
        ax.annotate(f'Total: {total:.0f}ms',
                   xy=(i, total),
                   xytext=(0, 5),
                   textcoords="offset points",
                   ha='center', va='bottom',
                   fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'component_breakdown.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: component_breakdown.png")


def create_summary_table(summary_local: dict, summary_aws: dict, output_dir: str):
    """Create a summary comparison table as an image"""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    
    metrics = [
        ('Total Tests', 'total_tests', ''),
        ('Successful Tests', 'successful_tests', ''),
        ('Failed Tests', 'failed_tests', ''),
        ('Cold Starts', 'cold_start_count', ''),
        ('Avg E2E Latency', 'avg_e2e_time_ms', 'ms'),
        ('P50 Latency', 'p50_e2e_ms', 'ms'),
        ('P95 Latency', 'p95_e2e_ms', 'ms'),
        ('P99 Latency', 'p99_e2e_ms', 'ms'),
        ('Throughput', 'throughput_files_per_sec', 'files/sec'),
    ]
    
    table_data = []
    for metric_name, key, unit, *formatter in metrics:
        if formatter:
            local_val = formatter[0](summary_local)
            aws_val = formatter[0](summary_aws)
        else:
            local_val = f"{summary_local.get(key, 'N/A'):.1f}{unit}" if isinstance(summary_local.get(key), (int, float)) else str(summary_local.get(key, 'N/A'))
            aws_val = f"{summary_aws.get(key, 'N/A'):.1f}{unit}" if isinstance(summary_aws.get(key), (int, float)) else str(summary_aws.get(key, 'N/A'))
        
        table_data.append([metric_name, local_val, aws_val])
    
    table = ax.table(
        cellText=table_data,
        colLabels=['Metric', 'LocalStack', 'AWS'],
        cellLoc='center',
        loc='center',
        colWidths=[0.4, 0.3, 0.3]
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Style header
    for i in range(3):
        table[(0, i)].set_facecolor('#34495e')
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    
    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(3):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#ecf0f1')
    
    ax.set_title('Performance Comparison Summary', fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'summary_table.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: summary_table.png")


def generate_all_charts(results_dir: str, output_dir: str):
    """Generate all charts"""
    
    print(f"\nLoading results from {results_dir}...")
    df_local, df_aws, summary_local, summary_aws = load_results(results_dir)
    
    if df_local.empty or df_aws.empty:
        print("Error: Could not load results from both environments.")
        print("Make sure you've run tests for both LocalStack and AWS.")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nGenerating charts to {output_dir}...")
    print("-" * 40)
    
    create_latency_comparison_chart(df_local, df_aws, output_dir)
    create_percentile_chart(summary_local, summary_aws, output_dir)
    create_throughput_chart(summary_local, summary_aws, output_dir)
    create_latency_by_file_size(df_local, df_aws, output_dir)
    create_latency_timeline(df_local, df_aws, output_dir)
    create_component_breakdown(df_local, df_aws, output_dir)
    create_summary_table(summary_local, summary_aws, output_dir)
    
    print("-" * 40)
    print(f"\nAll charts saved to {output_dir}/")
    print("\nCharts created:")
    for f in sorted(os.listdir(output_dir)):
        if f.endswith('.png'):
            print(f"  - {f}")


def main():
    parser = argparse.ArgumentParser(description='Generate analysis charts')
    parser.add_argument('--results', '-r', type=str, default='analysis/results',
                        help='Directory containing test results (default: analysis/results)')
    parser.add_argument('--output', '-o', type=str, default='analysis/charts',
                        help='Output directory for charts (default: analysis/charts)')
    
    args = parser.parse_args()
    generate_all_charts(args.results, args.output)


if __name__ == "__main__":
    main()
"""
Download Azure OpenAI diagnostic logs from Storage Account and process them.

This script:
1. Connects to Azure Storage Account
2. Downloads all logs from insights-logs-requestresponse container
3. Processes them into CSV format for PTU Calculator
4. Generates summary statistics

Usage:
    python3 download_azure_logs.py --storage-account nvstrgitentint --container insights-logs-requestresponse
    
    # With connection string
    export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
    python3 download_azure_logs.py
    
    # With account key
    python3 download_azure_logs.py --storage-account nvstrgitentint --account-key "your-key"
"""

import argparse
import json
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("ERROR: Azure Storage SDK not installed")
    print("Install it with: pip install azure-storage-blob azure-identity")
    sys.exit(1)


def parse_properties(properties_str):
    """Parse the properties JSON string."""
    try:
        return json.loads(properties_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_tokens_from_log(log_entry):
    """Extract token information from a log entry.
    
    Returns:
        tuple: (timestamp, input_tokens, output_tokens, total_tokens, model, result) or None
    """
    if log_entry.get('operationName') != 'ChatCompletions_Create':
        return None
    
    result_code = log_entry.get('resultSignature', '')
    timestamp_str = log_entry.get('time')
    
    if not timestamp_str:
        return None
    
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        formatted_time = dt.strftime("%-m/%-d/%Y, %-I:%M:%S.%f %p")
    except (ValueError, AttributeError):
        return None
    
    # Parse properties
    properties_str = log_entry.get('properties', '{}')
    props = parse_properties(properties_str)
    
    # Check for actual token counts (unlikely but worth checking)
    prompt_tokens = props.get('prompt_tokens') or props.get('promptTokens')
    completion_tokens = props.get('completion_tokens') or props.get('completionTokens')
    
    if prompt_tokens is not None and completion_tokens is not None:
        input_tokens = int(prompt_tokens)
        output_tokens = int(completion_tokens)
        total_tokens = input_tokens + output_tokens
    else:
        # Estimate from byte lengths
        request_length = props.get('requestLength', 0)
        response_length = props.get('responseLength', 0)
        
        if not request_length and not response_length:
            return None
        
        CHARS_PER_TOKEN = 3.5
        estimated_content_length = max(0, request_length - 200)
        input_tokens = max(1, int(estimated_content_length / CHARS_PER_TOKEN)) if request_length else 0
        
        estimated_response_content = max(0, response_length - 100)
        output_tokens = max(1, int(estimated_response_content / CHARS_PER_TOKEN)) if response_length else 0
        
        total_tokens = input_tokens + output_tokens
        
        if total_tokens == 0:
            return None
    
    model = props.get('modelDeploymentName', props.get('modelName', 'unknown'))
    model_version = props.get('modelVersion', 'unknown')
    
    return (formatted_time, input_tokens, output_tokens, total_tokens, model, model_version, result_code)


def download_and_process_container(blob_service_client, container_name, output_dir):
    """Download all blobs from container and process them.
    
    Returns:
        tuple: (all_rows, stats_dict)
    """
    print(f"\n📦 Processing container: {container_name}")
    
    container_client = blob_service_client.get_container_client(container_name)
    
    try:
        blobs = list(container_client.list_blobs())
        print(f"Found {len(blobs)} blobs in container")
    except Exception as e:
        print(f"ERROR: Could not list blobs: {e}")
        return [], {}
    
    if not blobs:
        print("No blobs found in container")
        return [], {}
    
    all_rows = []
    stats = {
        'total_logs': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'models': defaultdict(int),
        'error_codes': defaultdict(int),
        'blobs_processed': 0,
        'blobs_failed': 0
    }
    
    # Process each blob
    for i, blob in enumerate(blobs, 1):
        print(f"Processing blob {i}/{len(blobs)}: {blob.name}", end='\r')
        
        try:
            blob_client = container_client.get_blob_client(blob.name)
            blob_data = blob_client.download_blob().readall()
            content = blob_data.decode('utf-8')
            
            # Parse NDJSON (one JSON object per line)
            for line in content.strip().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    log_entry = json.loads(line)
                    stats['total_logs'] += 1
                    
                    result = extract_tokens_from_log(log_entry)
                    
                    if result:
                        timestamp, input_t, output_t, total_t, model, model_version, result_code = result
                        all_rows.append((timestamp, input_t, output_t, total_t, model, model_version))
                        
                        if result_code == '200':
                            stats['successful_requests'] += 1
                            stats['models'][model] += 1
                        else:
                            stats['failed_requests'] += 1
                            stats['error_codes'][result_code] += 1
                    else:
                        # Track failed/skipped entries
                        result_code = log_entry.get('resultSignature', 'unknown')
                        if result_code != '200':
                            stats['failed_requests'] += 1
                            stats['error_codes'][result_code] += 1
                        
                except json.JSONDecodeError:
                    continue
            
            stats['blobs_processed'] += 1
            
        except Exception as e:
            print(f"\nWarning: Failed to process blob {blob.name}: {e}")
            stats['blobs_failed'] += 1
            continue
    
    print(f"\n✅ Processed {stats['blobs_processed']} blobs successfully")
    
    return all_rows, stats


def write_csv(rows, output_path):
    """Write rows to CSV file."""
    print(f"\n📝 Writing CSV to: {output_path}")
    
    # Sort by timestamp
    rows.sort(key=lambda x: x[0])
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens', 'model', 'model_version'])
        
        for timestamp, input_t, output_t, total_t, model, model_version in rows:
            writer.writerow([timestamp, input_t, output_t, total_t, model, model_version])
    
    print(f"✅ Wrote {len(rows)} rows to CSV")


def generate_report(stats, rows, output_path):
    """Generate analysis report."""
    report_path = output_path.replace('.csv', '_report.txt')
    
    print(f"\n📊 Generating report: {report_path}")
    
    with open(report_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("Azure OpenAI Logs Analysis Report\n")
        f.write("="*80 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Overall stats
        f.write("OVERALL STATISTICS\n")
        f.write("-"*80 + "\n")
        f.write(f"Total log entries processed: {stats['total_logs']:,}\n")
        f.write(f"Successful requests (200): {stats['successful_requests']:,}\n")
        f.write(f"Failed requests: {stats['failed_requests']:,}\n")
        f.write(f"Blobs processed: {stats['blobs_processed']:,}\n")
        f.write(f"Blobs failed: {stats['blobs_failed']:,}\n\n")
        
        # Error codes
        if stats['error_codes']:
            f.write("ERROR CODES\n")
            f.write("-"*80 + "\n")
            for code, count in sorted(stats['error_codes'].items()):
                f.write(f"  {code}: {count:,} requests\n")
            f.write("\n")
        
        # Models
        if stats['models']:
            f.write("MODELS USED\n")
            f.write("-"*80 + "\n")
            for model, count in sorted(stats['models'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {model}: {count:,} requests\n")
            f.write("\n")
        
        # Token statistics
        if rows:
            total_input = sum(r[1] for r in rows)
            total_output = sum(r[2] for r in rows)
            total_tokens = sum(r[3] for r in rows)
            
            f.write("TOKEN STATISTICS (ESTIMATED)\n")
            f.write("-"*80 + "\n")
            f.write(f"Total input tokens: {total_input:,}\n")
            f.write(f"Total output tokens: {total_output:,}\n")
            f.write(f"Total tokens: {total_tokens:,}\n")
            f.write(f"Average tokens per request: {total_tokens/len(rows):,.0f}\n")
            f.write(f"Average input per request: {total_input/len(rows):,.0f}\n")
            f.write(f"Average output per request: {total_output/len(rows):,.0f}\n\n")
            
            # Time range
            timestamps = [datetime.strptime(r[0], "%-m/%-d/%Y, %-I:%M:%S.%f %p") for r in rows]
            min_time = min(timestamps)
            max_time = max(timestamps)
            duration_days = (max_time - min_time).total_seconds() / 86400
            
            f.write("TIME RANGE\n")
            f.write("-"*80 + "\n")
            f.write(f"First request: {min_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Last request: {max_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {duration_days:.1f} days\n\n")
            
            # Extrapolation to monthly
            if duration_days > 0:
                monthly_tokens = int(total_tokens * (30 / duration_days))
                monthly_requests = int(len(rows) * (30 / duration_days))
                
                f.write("MONTHLY PROJECTION\n")
                f.write("-"*80 + "\n")
                f.write(f"Projected monthly tokens: {monthly_tokens:,}\n")
                f.write(f"Projected monthly requests: {monthly_requests:,}\n\n")
        
        # Warnings
        f.write("⚠️  IMPORTANT NOTES\n")
        f.write("-"*80 + "\n")
        f.write("1. Token counts are ESTIMATES based on byte lengths (~3.5 chars/token)\n")
        f.write("2. Actual token usage may vary by ±25-30%\n")
        f.write("3. For production PTU planning, collect real token data from API responses\n")
        f.write("4. Add 1.3-1.5x safety buffer to PTU capacity calculations\n")
        f.write("5. Failed requests are excluded from token statistics\n\n")
        
        # Next steps
        f.write("NEXT STEPS\n")
        f.write("-"*80 + "\n")
        f.write("1. Upload the CSV file to the PTU Calculator app\n")
        f.write("2. Review the analysis with the understanding that tokens are estimated\n")
        f.write("3. Implement application-level token logging for accurate data\n")
        f.write("4. Re-analyze with real token counts before making PTU commitments\n")
    
    print(f"✅ Report generated")


def main():
    parser = argparse.ArgumentParser(description='Download and process Azure OpenAI logs')
    parser.add_argument('--storage-account', default='nvstrgitentint', help='Storage account name')
    parser.add_argument('--container', default='standard', help='Container name')
    parser.add_argument('--account-key', help='Storage account key')
    parser.add_argument('--connection-string', help='Storage connection string')
    parser.add_argument('--use-aad', action='store_true', help='Use Azure AD authentication (DefaultAzureCredential)')
    parser.add_argument('--account-url', help='Storage account URL (e.g., https://account.blob.core.windows.net/)')
    parser.add_argument('--output', default='azure_logs_analysis.csv', help='Output CSV filename')
    parser.add_argument('--output-dir', default='./analysis_output', help='Output directory')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / args.output
    
    print("="*80)
    print("Azure OpenAI Logs Analyzer")
    print("="*80)
    print(f"Storage Account: {args.storage_account}")
    print(f"Container: {args.container}")
    print(f"Output: {output_path}")
    
    # Connect to Azure Storage
    try:
        if args.use_aad or args.account_url:
            # Use Azure AD authentication
            account_url = args.account_url or f"https://{args.storage_account}.blob.core.windows.net/"
            print(f"Using Azure AD authentication with DefaultAzureCredential")
            print(f"Account URL: {account_url}")
            
            credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
            print("✅ Connected to Azure Storage with Azure AD")
            
        elif args.connection_string:
            connection_string = args.connection_string
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            print("✅ Connected to Azure Storage with connection string")
            
        elif os.environ.get('AZURE_STORAGE_CONNECTION_STRING'):
            connection_string = os.environ['AZURE_STORAGE_CONNECTION_STRING']
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            print("✅ Connected to Azure Storage with connection string from environment")
            
        elif args.account_key:
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={args.storage_account};"
                f"AccountKey={args.account_key};"
                f"EndpointSuffix=core.windows.net"
            )
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            print("✅ Connected to Azure Storage with account key")
            
        else:
            print("\n❌ ERROR: No authentication provided!")
            print("\nProvide one of:")
            print("  1. --use-aad (for Azure AD authentication)")
            print("  2. --account-url 'https://account.blob.core.windows.net/' --use-aad")
            print("  3. --connection-string 'DefaultEndpointsProtocol=https;...'")
            print("  4. --account-key 'your-key'")
            print("  5. Set environment variable: AZURE_STORAGE_CONNECTION_STRING")
            print("\nFor Azure AD authentication, ensure you're logged in:")
            print("  az login")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to Azure Storage: {e}")
        sys.exit(1)
    
    # Download and process logs
    try:
        rows, stats = download_and_process_container(
            blob_service_client,
            args.container,
            output_dir
        )
        
        if not rows:
            print("\n⚠️  WARNING: No valid token data found!")
            print("This could mean:")
            print("  - Container is empty")
            print("  - No successful ChatCompletions requests")
            print("  - All requests failed or were filtered out")
            sys.exit(1)
        
        # Write CSV
        write_csv(rows, str(output_path))
        
        # Generate report
        generate_report(stats, rows, str(output_path))
        
        print("\n" + "="*80)
        print("✅ ANALYSIS COMPLETE")
        print("="*80)
        print(f"CSV File: {output_path}")
        print(f"Report: {str(output_path).replace('.csv', '_report.txt')}")
        print(f"\nProcessed: {stats['successful_requests']:,} successful requests")
        print(f"Total tokens (estimated): {sum(r[3] for r in rows):,}")
        print(f"\n📊 Upload {output_path.name} to the PTU Calculator app!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

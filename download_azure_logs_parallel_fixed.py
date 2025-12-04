"""
Fixed parallel Azure logs downloader - simplified authentication.
"""

import argparse
import json
import csv
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("ERROR: Azure Storage SDK not installed")
    sys.exit(1)


def parse_properties(properties_str):
    """Parse the properties JSON string."""
    try:
        return json.loads(properties_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_tokens_from_log(log_entry):
    """Extract token information from a log entry."""
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
    
    properties_str = log_entry.get('properties', '{}')
    props = parse_properties(properties_str)
    
    # Check for actual token counts
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


def process_single_blob(blob_name, container_client):
    """Process a single blob using shared container client."""
    try:
        blob_client = container_client.get_blob_client(blob_name)
        blob_data = blob_client.download_blob().readall()
        
        # Process NDJSON
        lines = blob_data.decode('utf-8').splitlines()
        entries = []
        status_counts = defaultdict(int)
        model_counts = defaultdict(int)
        
        for line in lines:
            if not line.strip():
                continue
            try:
                log_entry = json.loads(line)
                result = extract_tokens_from_log(log_entry)
                
                if result:
                    entries.append(result)
                    _, _, _, _, model, model_version, result_code = result
                    status_counts[result_code] += 1
                    model_key = f"{model} ({model_version})" if model_version != 'unknown' else model
                    model_counts[model_key] += 1
                        
            except json.JSONDecodeError:
                continue
        
        return {
            'success': True,
            'blob_name': blob_name,
            'entries': entries,
            'status_counts': dict(status_counts),
            'model_counts': dict(model_counts)
        }
        
    except Exception as e:
        return {
            'success': False,
            'blob_name': blob_name,
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Download and process Azure OpenAI logs in parallel (ThreadPool version)")
    parser.add_argument('--storage-account', required=True, help='Azure Storage Account name')
    parser.add_argument('--container', default='insights-logs-requestresponse', help='Container name')
    parser.add_argument('--output-dir', default='./analysis_output', help='Output directory')
    parser.add_argument('--workers', type=int, default=50, help='Number of parallel workers')
    parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"THREAD-BASED PARALLEL AZURE LOG PROCESSOR")
    print(f"{'='*80}")
    print(f"Storage Account: {args.storage_account}")
    print(f"Container: {args.container}")
    print(f"Workers: {args.workers}")
    print(f"Output Directory: {args.output_dir}")
    print(f"{'='*80}\n")
    
    # Single authentication for all threads
    print("Authenticating with Azure...")
    credential = DefaultAzureCredential()
    account_url = f"https://{args.storage_account}.blob.core.windows.net"
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    container_client = blob_service.get_container_client(args.container)
    
    # List all blobs
    print("Listing all blobs in container...")
    blobs = list(container_client.list_blobs())
    total_blobs = len(blobs)
    print(f"Found {total_blobs:,} blobs to process\n")
    
    if total_blobs == 0:
        print("No blobs found!")
        return
    
    # Process with thread pool (threads share authentication)
    print(f"Starting parallel processing with {args.workers} workers...")
    print(f"Using ThreadPoolExecutor (threads share authentication)\n")
    
    start_time = time.time()
    all_entries = []
    global_status_counts = defaultdict(int)
    global_model_counts = defaultdict(int)
    success_count = 0
    fail_count = 0
    processed_count = 0
    
    # Use ThreadPoolExecutor instead of multiprocessing
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_blob = {
            executor.submit(process_single_blob, blob.name, container_client): blob.name 
            for blob in blobs
        }
        
        # Process completed tasks
        for future in as_completed(future_to_blob):
            blob_name = future_to_blob[future]
            processed_count += 1
            
            try:
                result = future.result()
                
                if result['success']:
                    success_count += 1
                    all_entries.extend(result['entries'])
                    
                    # Merge counts
                    for status, count in result['status_counts'].items():
                        global_status_counts[status] += count
                    for model, count in result['model_counts'].items():
                        global_model_counts[model] += count
                else:
                    fail_count += 1
                    print(f"⚠️  Failed: {result['blob_name']} - {result['error']}")
                
                # Progress update every 100 blobs
                if processed_count % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = processed_count / elapsed if elapsed > 0 else 0
                    remaining = total_blobs - processed_count
                    eta_seconds = remaining / rate if rate > 0 else 0
                    
                    print(f"Progress: {processed_count:,}/{total_blobs:,} blobs ({processed_count/total_blobs*100:.1f}%) | "
                          f"Entries: {len(all_entries):,} | "
                          f"Rate: {rate:.1f} blobs/sec | "
                          f"ETA: {eta_seconds/3600:.1f}h")
                    
            except Exception as e:
                fail_count += 1
                print(f"⚠️  Exception processing {blob_name}: {e}")
    
    elapsed_time = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total time: {elapsed_time/3600:.2f} hours ({elapsed_time/60:.1f} minutes)")
    print(f"Blobs processed: {success_count:,}/{total_blobs:,} ({success_count/total_blobs*100:.2f}%)")
    print(f"Blobs failed: {fail_count:,} ({fail_count/total_blobs*100:.2f}%)")
    print(f"Total entries: {len(all_entries):,}")
    print(f"Processing rate: {total_blobs/(elapsed_time/3600):.0f} blobs/hour")
    print(f"{'='*80}\n")
    
    if not all_entries:
        print("No valid entries found!")
        return
    
    # Sort entries by timestamp
    print("Sorting entries by timestamp...")
    all_entries.sort(key=lambda x: x[0])
    
    # Write CSV
    csv_path = output_dir / f"{args.storage_account}_complete_analysis_with_models.csv"
    print(f"\nWriting CSV to: {csv_path}")
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens', 'model', 'model_version', 'result_code'])
        writer.writerows(all_entries)
    
    csv_size_mb = csv_path.stat().st_size / (1024 * 1024)
    print(f"✅ CSV written: {len(all_entries):,} rows, {csv_size_mb:.1f} MB")
    
    # Print model summary
    print(f"\n{'='*80}")
    print("MODEL SUMMARY")
    print(f"{'='*80}")
    for model, count in sorted(global_model_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {model}: {count:,} requests")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

"""
Extract Azure OpenAI usage data from RequestResponse logs in Azure Storage.
This script reads the diagnostic logs and extracts token usage information.
"""

import json
import pandas as pd
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import re

# Configuration
STORAGE_ACCOUNT_NAME = "your-storage-account"
STORAGE_ACCOUNT_URL = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
CONTAINER_NAME = "insights-logs-requestresponse"
OUTPUT_FILE = "azure_openai_usage.csv"

def get_blob_service_client():
    """Create blob service client using Azure AD authentication"""
    credential = DefaultAzureCredential()
    return BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)

def parse_log_entry(log_line):
    """Parse a single log line and extract token information"""
    try:
        record = json.loads(log_line)
        
        # Extract basic info
        timestamp = record.get('time', '')
        operation = record.get('operationName', '')
        properties_str = record.get('properties', '{}')
        
        # Parse properties JSON string
        try:
            properties = json.loads(properties_str)
        except:
            return None
        
        # Only process successful chat completions and embeddings
        if operation not in ['ChatCompletions_Create', 'Embeddings_Create']:
            return None
        
        # Extract model info
        model_name = properties.get('modelName', '')
        model_deployment = properties.get('modelDeploymentName', '')
        
        # Try to extract token counts from request/response lengths
        # For chat completions, we need to estimate based on lengths
        request_length = properties.get('requestLength', 0)
        response_length = properties.get('responseLength', 0)
        
        # Rough estimation: 4 characters per token (this is approximate)
        # Better would be to get actual token counts from the API response
        est_input_tokens = request_length // 4
        est_output_tokens = response_length // 4
        
        return {
            'timestamp [UTC]': timestamp,
            'input_tokens': est_input_tokens,
            'output_tokens': est_output_tokens,
            'total_tokens': est_input_tokens + est_output_tokens,
            'operation': operation,
            'model': model_name,
            'deployment': model_deployment
        }
        
    except Exception as e:
        return None

def download_and_process_blobs(blob_service_client, max_blobs=500):
    """Download and process RequestResponse log blobs"""
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    
    print(f"Fetching blob list from container: {CONTAINER_NAME}")
    
    # List all blobs, focusing on recent OpenAI ones
    all_blobs = []
    for blob in container_client.list_blobs():
        if 'OPENAI' in blob.name.upper():
            all_blobs.append(blob)
    
    # Sort by last modified (newest first) and limit
    all_blobs.sort(key=lambda x: x.last_modified, reverse=True)
    blobs_to_process = all_blobs[:max_blobs]
    
    print(f"Found {len(all_blobs)} OpenAI log blobs, processing {len(blobs_to_process)}")
    
    all_records = []
    
    for idx, blob in enumerate(blobs_to_process, 1):
        if idx % 50 == 0:
            print(f"  Processed {idx}/{len(blobs_to_process)} blobs, {len(all_records)} records extracted")
        
        try:
            # Download blob content
            blob_client = container_client.get_blob_client(blob.name)
            data = blob_client.download_blob().readall()
            
            # Process each line (JSON lines format)
            for line in data.decode('utf-8').strip().split('\n'):
                if not line:
                    continue
                
                parsed = parse_log_entry(line)
                if parsed and parsed['total_tokens'] > 0:
                    all_records.append(parsed)
                    
        except Exception as e:
            print(f"  Warning: Could not process blob {blob.name}: {e}")
            continue
    
    print(f"\nTotal records extracted: {len(all_records)}")
    return all_records

def format_timestamp(timestamp_str):
    """Convert ISO timestamp to simulator format"""
    try:
        # Parse: 2025-11-04T02:03:59.9910000Z
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # Format: 8/18/2025, 12:00:38.941 AM
        month = dt.month
        day = dt.day
        year = dt.year
        hour12 = dt.hour % 12
        if hour12 == 0:
            hour12 = 12
        am_pm = 'AM' if dt.hour < 12 else 'PM'
        millisecond = dt.microsecond // 1000
        
        return f"{month}/{day}/{year}, {hour12}:{dt.minute:02d}:{dt.second:02d}.{millisecond:03d} {am_pm}"
    except:
        return timestamp_str

def save_to_csv(records, output_file):
    """Save records to CSV in the required format"""
    if not records:
        print("No records to save!")
        return False
    
    df = pd.DataFrame(records)
    
    # Format timestamps
    print("Formatting timestamps...")
    df['timestamp [UTC]'] = df['timestamp [UTC]'].apply(format_timestamp)
    
    # Select only required columns
    required_cols = ['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']
    df_output = df[required_cols].copy()
    
    # Sort by timestamp
    df_output = df_output.sort_values('timestamp [UTC]')
    
    # Save to CSV
    df_output.to_csv(output_file, index=False)
    print(f"\n✓ Saved {len(df_output)} records to {output_file}")
    
    # Print sample data
    print("\nSample data (first 5 rows):")
    print(df_output.head().to_string(index=False))
    
    # Print statistics
    print(f"\nStatistics:")
    print(f"  Total requests: {len(df_output):,}")
    print(f"  Total input tokens (estimated): {df_output['input_tokens'].sum():,}")
    print(f"  Total output tokens (estimated): {df_output['output_tokens'].sum():,}")
    print(f"  Total tokens (estimated): {df_output['total_tokens'].sum():,}")
    print(f"  Date range: {df_output['timestamp [UTC]'].min()} to {df_output['timestamp [UTC]'].max()}")
    
    # Model breakdown
    print(f"\nModel breakdown:")
    model_summary = df.groupby('model')['total_tokens'].agg(['count', 'sum'])
    print(model_summary)
    
    return True

def main():
    print(f"{'='*60}")
    print("Azure OpenAI Usage Data Extractor")
    print(f"{'='*60}")
    print(f"Storage Account: {STORAGE_ACCOUNT_NAME}")
    print(f"Container: {CONTAINER_NAME}")
    print()
    
    try:
        print("Connecting to Azure Storage...")
        blob_service_client = get_blob_service_client()
        
        print("\nDownloading and processing RequestResponse logs...")
        print("NOTE: Token counts are estimated from request/response sizes")
        print("      (actual token counts may vary)")
        print()
        
        records = download_and_process_blobs(blob_service_client, max_blobs=500)
        
        if records:
            success = save_to_csv(records, OUTPUT_FILE)
            if success:
                print(f"\n{'='*60}")
                print("✓ SUCCESS!")
                print(f"{'='*60}")
                print(f"\nYou can now upload '{OUTPUT_FILE}' to the PTU simulator.")
                print("\nIMPORTANT: Token counts are estimated from request/response byte sizes.")
                print("For production analysis, consider using actual token count APIs.")
        else:
            print("\nNo usage records found!")
            print("The logs may not contain processable data.")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure you have:")
        print("  1. Logged in with 'az login'")
        print("  2. Storage Blob Data Reader role on the storage account")
        print("  3. Public network access enabled on the storage account")

if __name__ == "__main__":
    main()

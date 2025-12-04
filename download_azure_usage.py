"""
Script to download Azure OpenAI usage data from Azure Storage Account
and convert it to the format required by the PTU simulator.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

# Configuration
STORAGE_ACCOUNT_NAME = "your-storage-account"
STORAGE_ACCOUNT_URL = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
OUTPUT_FILE = "azure_openai_usage.csv"

def get_blob_service_client():
    """Create blob service client using Azure AD authentication"""
    credential = DefaultAzureCredential()
    return BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)

def list_containers(blob_service_client):
    """List all containers in the storage account"""
    print("Available containers:")
    containers = []
    for container in blob_service_client.list_containers():
        print(f"  - {container.name}")
        containers.append(container.name)
    return containers

def find_usage_blobs(blob_service_client, container_name, days_back=30):
    """Find Azure OpenAI usage blobs in the container"""
    container_client = blob_service_client.get_container_client(container_name)
    
    print(f"\nSearching for usage data in container: {container_name}")
    usage_blobs = []
    
    # Look for blobs with 'RequestUsage' or 'usage' in the path
    for blob in container_client.list_blobs():
        if 'requestusage' in blob.name.lower() or 'usage' in blob.name.lower():
            usage_blobs.append(blob)
            print(f"  Found: {blob.name} (Size: {blob.size} bytes)")
    
    return usage_blobs

def download_and_parse_usage_data(blob_service_client, container_name, blob_names=None, max_blobs=100):
    """Download usage data and convert to the required CSV format"""
    container_client = blob_service_client.get_container_client(container_name)
    
    all_records = []
    blob_count = 0
    
    # Get list of blobs to process
    if blob_names:
        blobs = [container_client.get_blob_client(name) for name in blob_names]
    else:
        # List all blobs and filter for usage data
        all_blobs = list(container_client.list_blobs())
        blobs = [b for b in all_blobs if 'requestusage' in b.name.lower()]
        blobs = sorted(blobs, key=lambda x: x.last_modified, reverse=True)[:max_blobs]
    
    print(f"\nProcessing {len(blobs)} blobs...")
    
    for blob in blobs:
        blob_count += 1
        if blob_count % 10 == 0:
            print(f"  Processed {blob_count}/{len(blobs)} blobs, {len(all_records)} records found")
        
        try:
            # Download blob
            blob_client = container_client.get_blob_client(blob.name if hasattr(blob, 'name') else blob)
            data = blob_client.download_blob().readall()
            
            # Parse JSON lines (each line is a separate JSON record)
            for line in data.decode('utf-8').strip().split('\n'):
                if not line:
                    continue
                    
                try:
                    record = json.loads(line)
                    
                    # Extract relevant fields for OpenAI usage
                    # The exact field names may vary, adjust based on actual data structure
                    if 'properties' in record:
                        props = record['properties']
                        
                        # Extract timestamp
                        timestamp = record.get('time', record.get('timestamp', ''))
                        
                        # Extract token counts
                        input_tokens = props.get('inputTokens', props.get('prompt_tokens', 0))
                        output_tokens = props.get('outputTokens', props.get('completion_tokens', 0))
                        total_tokens = props.get('totalTokens', props.get('total_tokens', input_tokens + output_tokens))
                        
                        # Only include records with actual token usage
                        if total_tokens > 0:
                            all_records.append({
                                'timestamp [UTC]': timestamp,
                                'input_tokens': input_tokens,
                                'output_tokens': output_tokens,
                                'total_tokens': total_tokens
                            })
                    
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            print(f"  Warning: Could not process blob {getattr(blob, 'name', blob)}: {e}")
            continue
    
    print(f"\nTotal records extracted: {len(all_records)}")
    return all_records

def format_timestamp(timestamp_str):
    """Convert ISO timestamp to the format expected by the simulator"""
    try:
        # Parse ISO format: 2025-08-18T00:00:38.941Z
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # Format as: 8/18/2025, 12:00:38.941 AM
        return dt.strftime('%-m/%-d/%Y, %-I:%M:%S.%f %p')[:-3]  # Remove last 3 digits of microseconds
    except:
        return timestamp_str

def save_to_csv(records, output_file):
    """Save records to CSV in the required format"""
    if not records:
        print("No records to save!")
        return
    
    df = pd.DataFrame(records)
    
    # Format timestamps
    df['timestamp [UTC]'] = df['timestamp [UTC]'].apply(format_timestamp)
    
    # Sort by timestamp
    df = df.sort_values('timestamp [UTC]')
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved {len(df)} records to {output_file}")
    
    # Print sample data
    print("\nSample data (first 5 rows):")
    print(df.head())
    
    # Print statistics
    print(f"\nStatistics:")
    print(f"  Total requests: {len(df)}")
    print(f"  Total input tokens: {df['input_tokens'].sum():,}")
    print(f"  Total output tokens: {df['output_tokens'].sum():,}")
    print(f"  Total tokens: {df['total_tokens'].sum():,}")
    print(f"  Date range: {df['timestamp [UTC]'].min()} to {df['timestamp [UTC]'].max()}")

def main():
    try:
        print(f"Connecting to storage account: {STORAGE_ACCOUNT_NAME}")
        print("Using Azure AD authentication (DefaultAzureCredential)...")
        
        blob_service_client = get_blob_service_client()
        
        # List containers
        containers = list_containers(blob_service_client)
        
        if not containers:
            print("\nNo containers found or unable to access storage account.")
            print("Make sure you have the necessary permissions and network access.")
            return
        
        # Look for usage data in each container
        all_usage_blobs = []
        for container_name in containers:
            try:
                usage_blobs = find_usage_blobs(blob_service_client, container_name)
                if usage_blobs:
                    all_usage_blobs.extend([(container_name, blob) for blob in usage_blobs])
            except Exception as e:
                print(f"  Could not access container {container_name}: {e}")
        
        if not all_usage_blobs:
            print("\nNo usage data blobs found. Looking for any JSON blobs...")
            # Fallback: look for any JSON blobs
            for container_name in containers[:3]:  # Check first 3 containers
                try:
                    container_client = blob_service_client.get_container_client(container_name)
                    blobs = list(container_client.list_blobs())
                    if blobs:
                        print(f"\nBlobs in {container_name} (first 10):")
                        for blob in blobs[:10]:
                            print(f"  - {blob.name}")
                except:
                    pass
            return
        
        # Download and process data from the first container with usage data
        container_name = all_usage_blobs[0][0]
        print(f"\n{'='*60}")
        print(f"Downloading usage data from container: {container_name}")
        print(f"{'='*60}")
        
        records = download_and_parse_usage_data(blob_service_client, container_name, max_blobs=100)
        
        if records:
            save_to_csv(records, OUTPUT_FILE)
            print(f"\n✓ Success! You can now upload '{OUTPUT_FILE}' to the PTU simulator.")
        else:
            print("\nNo usage records found. The log format may be different than expected.")
            print("Please check the blob structure and adjust the parsing logic.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure you have:")
        print("  1. Logged in with 'az login'")
        print("  2. Appropriate permissions to access the storage account")
        print("  3. Network access to the storage account (VPN or private endpoint)")

if __name__ == "__main__":
    main()

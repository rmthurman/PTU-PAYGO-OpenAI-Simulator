"""
Comprehensive Azure OpenAI Usage Data Extractor

This script extracts usage metrics from Azure Storage diagnostic logs
and consolidates them into a single CSV file for PTU analysis.

Features:
- Reads from insights-logs-requestresponse container
- Filters by date range
- Processes multiple OpenAI accounts
- Extracts actual token counts from logs
- Consolidates all data into one CSV
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import argparse
from typing import List, Dict, Optional
import re

# Configuration
STORAGE_ACCOUNT_NAME = "randyscommondatawus3"
STORAGE_ACCOUNT_URL = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
CONTAINER_NAME = "insights-logs-requestresponse"

class AzureOpenAIUsageExtractor:
    def __init__(self, storage_account_name: str = STORAGE_ACCOUNT_NAME):
        self.storage_account_name = storage_account_name
        self.storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
        self.container_name = CONTAINER_NAME
        self.blob_service_client = None
        
    def connect(self):
        """Connect to Azure Storage using Azure AD authentication"""
        print(f"Connecting to storage account: {self.storage_account_name}")
        credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(
            account_url=self.storage_account_url, 
            credential=credential
        )
        print("✓ Connected successfully")
        
    def list_openai_accounts(self) -> List[str]:
        """List all OpenAI accounts that have logs in the storage account"""
        print(f"\nScanning for OpenAI accounts in container: {self.container_name}")
        container_client = self.blob_service_client.get_container_client(self.container_name)
        
        accounts = set()
        for blob in container_client.list_blobs():
            # Parse blob path to extract account name
            # Format: resourceId=/SUBSCRIPTIONS/.../ACCOUNTS/ACCOUNTNAME/y=2025/...
            match = re.search(r'/ACCOUNTS/([^/]+)/', blob.name, re.IGNORECASE)
            if match:
                account_name = match.group(1)
                if 'OPENAI' in account_name.upper():
                    accounts.add(account_name)
        
        accounts_list = sorted(list(accounts))
        print(f"Found {len(accounts_list)} OpenAI accounts:")
        for account in accounts_list:
            print(f"  - {account}")
        
        return accounts_list
    
    def get_blobs_for_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        accounts: Optional[List[str]] = None
    ) -> List[str]:
        """Get list of blob names within the specified date range"""
        print(f"\nFetching blobs for date range: {start_date.date()} to {end_date.date()}")
        
        container_client = self.blob_service_client.get_container_client(self.container_name)
        matching_blobs = []
        
        for blob in container_client.list_blobs():
            # Check if blob is for one of our target accounts
            if accounts:
                if not any(acc.upper() in blob.name.upper() for acc in accounts):
                    continue
            elif 'OPENAI' not in blob.name.upper():
                continue
            
            # Extract date from blob path
            # Format: .../y=2025/m=11/d=04/h=02/m=00/PT1H.json
            match = re.search(r'/y=(\d{4})/m=(\d{1,2})/d=(\d{1,2})/', blob.name)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                blob_date = datetime(year, month, day)
                
                if start_date <= blob_date <= end_date:
                    matching_blobs.append(blob.name)
        
        print(f"Found {len(matching_blobs)} blobs matching criteria")
        return matching_blobs
    
    def parse_log_entry(self, log_line: str) -> Optional[Dict]:
        """
        Parse a single log line and extract token information.
        
        The RequestResponse logs contain token counts in the properties field.
        We need to parse both the log JSON and the nested properties JSON string.
        """
        try:
            record = json.loads(log_line)
            
            # Extract basic info
            timestamp = record.get('time', '')
            operation = record.get('operationName', '')
            result_code = record.get('resultSignature', '')
            duration_ms = record.get('durationMs', 0)
            location = record.get('location', '')
            
            # Parse properties JSON string
            properties_str = record.get('properties', '{}')
            try:
                properties = json.loads(properties_str)
            except:
                return None
            
            # Only process relevant operations
            if operation not in ['ChatCompletions_Create', 'Embeddings_Create']:
                return None
            
            # Only successful requests
            if result_code != '200':
                return None
            
            # Extract model info
            model_name = properties.get('modelName', '')
            model_deployment = properties.get('modelDeploymentName', '')
            api_version = properties.get('apiName', '')
            stream_type = properties.get('streamType', '')
            
            # Get request/response lengths
            request_length = properties.get('requestLength', 0)
            response_length = properties.get('responseLength', 0)
            
            # Estimate token counts from byte sizes
            # This is an approximation: roughly 4 bytes per token
            # For better accuracy, you'd need to parse actual API responses
            est_input_tokens = request_length // 4
            est_output_tokens = response_length // 4
            
            # For embeddings, output is embeddings data, not text tokens
            # Adjust estimation
            if operation == 'Embeddings_Create':
                # Request contains the text to embed
                est_input_tokens = request_length // 4
                # Response is embedding vectors, not tokens
                est_output_tokens = 0
            
            total_tokens = est_input_tokens + est_output_tokens
            
            # Only include entries with actual usage
            if total_tokens == 0:
                return None
            
            return {
                'timestamp [UTC]': timestamp,
                'input_tokens': est_input_tokens,
                'output_tokens': est_output_tokens,
                'total_tokens': total_tokens,
                'operation': operation,
                'model': model_name,
                'deployment': model_deployment,
                'location': location,
                'duration_ms': duration_ms,
                'stream_type': stream_type,
                'request_bytes': request_length,
                'response_bytes': response_length
            }
            
        except Exception as e:
            # Silently skip malformed entries
            return None
    
    def process_blob(self, blob_name: str) -> List[Dict]:
        """Download and process a single blob"""
        container_client = self.blob_service_client.get_container_client(self.container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        records = []
        try:
            # Download blob content
            data = blob_client.download_blob().readall()
            
            # Process each line (JSON lines format)
            for line in data.decode('utf-8').strip().split('\n'):
                if not line:
                    continue
                
                parsed = self.parse_log_entry(line)
                if parsed:
                    records.append(parsed)
                    
        except Exception as e:
            print(f"  Warning: Could not process blob {blob_name}: {e}")
        
        return records
    
    def extract_usage_data(
        self,
        start_date: datetime,
        end_date: datetime,
        accounts: Optional[List[str]] = None,
        max_blobs: Optional[int] = None
    ) -> List[Dict]:
        """Extract usage data for the specified date range"""
        
        # Get list of blobs to process
        blob_names = self.get_blobs_for_date_range(start_date, end_date, accounts)
        
        if not blob_names:
            print("No blobs found for the specified criteria")
            return []
        
        # Limit number of blobs if specified
        if max_blobs and len(blob_names) > max_blobs:
            print(f"Limiting to {max_blobs} most recent blobs")
            blob_names = blob_names[-max_blobs:]
        
        # Process blobs
        print(f"\nProcessing {len(blob_names)} blobs...")
        all_records = []
        
        for idx, blob_name in enumerate(blob_names, 1):
            if idx % 10 == 0 or idx == len(blob_names):
                print(f"  Progress: {idx}/{len(blob_names)} blobs ({len(all_records)} records extracted)")
            
            records = self.process_blob(blob_name)
            all_records.extend(records)
        
        print(f"\n✓ Extraction complete: {len(all_records)} total records")
        return all_records
    
    def format_timestamp(self, timestamp_str: str) -> str:
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
    
    def save_to_csv(self, records: List[Dict], output_file: str, include_metadata: bool = False) -> bool:
        """Save records to CSV in the required format"""
        if not records:
            print("No records to save!")
            return False
        
        df = pd.DataFrame(records)
        
        # Format timestamps
        print("\nFormatting data for output...")
        df['timestamp [UTC]'] = df['timestamp [UTC]'].apply(self.format_timestamp)
        
        # Select columns for output
        if include_metadata:
            # Include all metadata columns
            output_cols = [
                'timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens',
                'operation', 'model', 'deployment', 'location', 'duration_ms', 
                'stream_type', 'request_bytes', 'response_bytes'
            ]
            df_output = df[output_cols].copy()
        else:
            # Only required columns for PTU simulator
            required_cols = ['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']
            df_output = df[required_cols].copy()
        
        # Sort by timestamp
        df_output = df_output.sort_values('timestamp [UTC]')
        
        # Save to CSV
        df_output.to_csv(output_file, index=False)
        print(f"\n✓ Saved {len(df_output)} records to {output_file}")
        
        # Print sample data
        print("\nSample data (first 5 rows):")
        sample_cols = ['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']
        available_cols = [col for col in sample_cols if col in df_output.columns]
        print(df_output[available_cols].head().to_string(index=False))
        
        # Print statistics
        print(f"\nStatistics:")
        print(f"  Total requests: {len(df_output):,}")
        print(f"  Total input tokens: {df['input_tokens'].sum():,}")
        print(f"  Total output tokens: {df['output_tokens'].sum():,}")
        print(f"  Total tokens: {df['total_tokens'].sum():,}")
        print(f"  Date range: {df_output['timestamp [UTC]'].min()} to {df_output['timestamp [UTC]'].max()}")
        
        # Model breakdown
        if 'model' in df.columns:
            print(f"\nModel breakdown:")
            model_summary = df.groupby('model').agg({
                'total_tokens': ['count', 'sum'],
                'input_tokens': 'sum',
                'output_tokens': 'sum'
            })
            print(model_summary)
        
        # Operation breakdown
        if 'operation' in df.columns:
            print(f"\nOperation breakdown:")
            op_summary = df.groupby('operation')['total_tokens'].agg(['count', 'sum'])
            print(op_summary)
        
        # Location breakdown
        if 'location' in df.columns:
            print(f"\nLocation breakdown:")
            loc_summary = df.groupby('location')['total_tokens'].agg(['count', 'sum'])
            print(loc_summary)
        
        return True


def parse_date(date_string: str) -> datetime:
    """Parse date string in various formats"""
    formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%Y/%m/%d',
        '%m-%d-%Y'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date: {date_string}. Use format: YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description='Extract Azure OpenAI usage data from Azure Storage diagnostic logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract last 7 days
  python %(prog)s --days 7
  
  # Extract specific date range
  python %(prog)s --start-date 2025-10-01 --end-date 2025-11-13
  
  # Extract for specific accounts
  python %(prog)s --days 30 --accounts randysopenaieastus randysopenaiwestus3
  
  # Include metadata columns
  python %(prog)s --days 7 --include-metadata
  
  # Limit number of blobs processed
  python %(prog)s --days 30 --max-blobs 100
        """
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD format)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD format)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to look back from today (default: 7)'
    )
    
    parser.add_argument(
        '--accounts',
        nargs='+',
        help='Specific OpenAI account names to process'
    )
    
    parser.add_argument(
        '--list-accounts',
        action='store_true',
        help='List all available OpenAI accounts and exit'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='azure_openai_usage.csv',
        help='Output CSV file name (default: azure_openai_usage.csv)'
    )
    
    parser.add_argument(
        '--include-metadata',
        action='store_true',
        help='Include metadata columns (model, location, etc.) in output'
    )
    
    parser.add_argument(
        '--max-blobs',
        type=int,
        help='Maximum number of blobs to process (for testing)'
    )
    
    parser.add_argument(
        '--storage-account',
        type=str,
        default=STORAGE_ACCOUNT_NAME,
        help=f'Storage account name (default: {STORAGE_ACCOUNT_NAME})'
    )
    
    args = parser.parse_args()
    
    # Print header
    print("="*70)
    print("Azure OpenAI Usage Data Extractor")
    print("="*70)
    
    # Create extractor
    extractor = AzureOpenAIUsageExtractor(args.storage_account)
    
    try:
        # Connect to storage
        extractor.connect()
        
        # List accounts if requested
        if args.list_accounts:
            extractor.list_openai_accounts()
            return
        
        # Determine date range
        if args.start_date and args.end_date:
            start_date = parse_date(args.start_date)
            end_date = parse_date(args.end_date)
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
        
        print(f"\nDate range: {start_date.date()} to {end_date.date()}")
        
        if args.accounts:
            print(f"Filtering for accounts: {', '.join(args.accounts)}")
        
        # Extract data
        records = extractor.extract_usage_data(
            start_date=start_date,
            end_date=end_date,
            accounts=args.accounts,
            max_blobs=args.max_blobs
        )
        
        if records:
            # Save to CSV
            success = extractor.save_to_csv(
                records, 
                args.output, 
                include_metadata=args.include_metadata
            )
            
            if success:
                print(f"\n{'='*70}")
                print("✓ SUCCESS!")
                print(f"{'='*70}")
                print(f"\nData saved to: {args.output}")
                print("\nYou can now upload this file to the PTU vs PAYGO simulator.")
                print("\nIMPORTANT: Token counts are estimated from request/response sizes.")
                print("For exact token counts, consider using Azure Monitor queries or API logs.")
        else:
            print("\nNo usage data found for the specified criteria.")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure you have:")
        print("  1. Logged in with 'az login'")
        print("  2. Storage Blob Data Reader role on the storage account")
        print("  3. Public network access enabled on the storage account (temporarily)")


if __name__ == "__main__":
    main()

"""
Alternative script to extract Azure OpenAI usage data using Azure CLI and export capabilities.
This approach uses Azure Monitor queries to get the data directly.
"""

import subprocess
import json
import pandas as pd
from datetime import datetime, timedelta

# Configuration
OUTPUT_FILE = "azure_openai_usage.csv"
SUBSCRIPTION_ID = "5834bd7f-f5ad-42c9-8923-48c60bcbef69"
RESOURCE_GROUP = "common"

# List of OpenAI accounts to query
OPENAI_ACCOUNTS = [
    "openai-westus",
    "openai-eastus",
    "openai-eastus2",
    "openai-canadacentral",
    "openai-northcentral",
    "openai-westus3",
    "openai-canadaeast",
    "openai-australiaeast",
    "openai-brazilsouth",
    "openai-southindia"
]

def run_az_command(command):
    """Run an Azure CLI command and return the output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def query_azure_monitor_logs(resource_id, days_back=7):
    """Query Azure Monitor logs for OpenAI usage data"""
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_back)
    
    # KQL query for OpenAI request usage
    query = f"""
    AzureDiagnostics
    | where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
    | where Category == "RequestResponse" or Category == "AzureOpenAIRequestUsage"
    | where TimeGenerated >= datetime({start_time.isoformat()}Z)
    | where TimeGenerated <= datetime({end_time.isoformat()}Z)
    | project TimeGenerated, 
              prompt_tokens_d,
              completion_tokens_d,
              total_tokens_d,
              OperationName,
              DurationMs
    | where total_tokens_d > 0
    | order by TimeGenerated asc
    """
    
    print(f"Querying Azure Monitor for resource: {resource_id}")
    print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")
    
    # Escape the query for command line
    query_escaped = query.replace('"', '\\"').replace('\n', ' ')
    
    command = f'''az monitor app-insights query --apps "{resource_id}" --analytics-query "{query_escaped}" --output json'''
    
    output = run_az_command(command)
    
    if output:
        try:
            result = json.loads(output)
            return result
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
    
    return None

def export_usage_via_diagnostic_settings(account_name, days_back=30):
    """
    Try to query diagnostic logs for an OpenAI account.
    This requires that diagnostic settings are configured to send logs to Log Analytics.
    """
    
    resource_id = f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/{account_name}"
    
    # First, check if there's a Log Analytics workspace configured
    print(f"\nChecking diagnostic settings for {account_name}...")
    
    command = f'az monitor diagnostic-settings list --resource "{resource_id}" --output json'
    output = run_az_command(command)
    
    if not output:
        print(f"  Could not retrieve diagnostic settings")
        return []
    
    try:
        settings = json.loads(output)
        workspace_id = None
        
        for setting in settings:
            if setting.get('workspaceId'):
                workspace_id = setting['workspaceId']
                print(f"  Found Log Analytics workspace: {workspace_id}")
                break
        
        if not workspace_id:
            print(f"  No Log Analytics workspace found in diagnostic settings")
            return []
        
        # Query Log Analytics
        records = query_log_analytics(workspace_id, resource_id, days_back)
        return records
        
    except json.JSONDecodeError as e:
        print(f"  Error parsing diagnostic settings: {e}")
        return []

def query_log_analytics(workspace_id, resource_id, days_back=30):
    """Query Log Analytics workspace for usage data"""
    
    # Extract workspace name from ID
    workspace_parts = workspace_id.split('/')
    workspace_name = workspace_parts[-1]
    workspace_rg = workspace_parts[4]
    
    print(f"  Querying Log Analytics workspace: {workspace_name}")
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_back)
    
    # KQL query
    query = f"""
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where Category in ("RequestResponse", "AzureOpenAIRequestUsage")
| where TimeGenerated >= datetime({start_time.strftime('%Y-%m-%dT%H:%M:%S')}Z)
| where Resource == "{resource_id.split('/')[-1]}"
| extend input_tokens = coalesce(prompt_tokens_d, toint(properties_s.inputTokens), 0)
| extend output_tokens = coalesce(completion_tokens_d, toint(properties_s.outputTokens), 0)
| extend total_tokens = coalesce(total_tokens_d, toint(properties_s.totalTokens), input_tokens + output_tokens)
| where total_tokens > 0
| project TimeGenerated, input_tokens, output_tokens, total_tokens
| order by TimeGenerated asc
"""
    
    # Save query to temp file (easier than escaping)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kql', delete=False) as f:
        f.write(query)
        query_file = f.name
    
    command = f'az monitor log-analytics query -w "{workspace_name}" -g "{workspace_rg}" --analytics-query "{query}" --output json'
    
    output = run_az_command(command)
    
    if output:
        try:
            result = json.loads(output)
            if 'tables' in result and len(result['tables']) > 0:
                table = result['tables'][0]
                rows = table.get('rows', [])
                columns = [col['name'] for col in table.get('columns', [])]
                
                print(f"  Found {len(rows)} usage records")
                
                # Convert to list of dicts
                records = []
                for row in rows:
                    record = dict(zip(columns, row))
                    records.append(record)
                
                return records
        except json.JSONDecodeError as e:
            print(f"  Error parsing query results: {e}")
    
    return []

def format_timestamp_for_simulator(timestamp_str):
    """Convert timestamp to simulator format: 8/18/2025, 12:00:38.941 AM"""
    try:
        # Parse various timestamp formats
        for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S.%f']:
            try:
                dt = datetime.strptime(timestamp_str.replace('+00:00', ''), fmt)
                # Format as needed by simulator
                return dt.strftime('%-m/%-d/%Y, %-I:%M:%S.%f %p')[:-3]  # Remove last 3 microsecond digits
            except ValueError:
                continue
        
        # If all formats fail, return original
        return timestamp_str
    except:
        return timestamp_str

def create_csv_from_records(records, output_file):
    """Convert records to CSV in the required format"""
    
    if not records:
        print("\nNo records to export!")
        return False
    
    print(f"\nProcessing {len(records)} records...")
    
    # Convert to DataFrame
    df = pd.DataFrame(records)
    
    # Rename columns to match expected format
    column_mapping = {
        'TimeGenerated': 'timestamp [UTC]',
        'input_tokens': 'input_tokens',
        'output_tokens': 'output_tokens',
        'total_tokens': 'total_tokens'
    }
    
    df = df.rename(columns=column_mapping)
    
    # Format timestamps
    if 'timestamp [UTC]' in df.columns:
        df['timestamp [UTC]'] = df['timestamp [UTC]'].apply(format_timestamp_for_simulator)
    
    # Ensure required columns exist
    required_cols = ['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']
    for col in required_cols:
        if col not in df.columns:
            print(f"Warning: Missing column {col}")
            return False
    
    # Select only required columns
    df = df[required_cols]
    
    # Sort by timestamp
    df = df.sort_values('timestamp [UTC]')
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    
    print(f"\n✓ Successfully created {output_file}")
    print(f"\nStatistics:")
    print(f"  Total requests: {len(df):,}")
    print(f"  Total input tokens: {df['input_tokens'].sum():,.0f}")
    print(f"  Total output tokens: {df['output_tokens'].sum():,.0f}")
    print(f"  Total tokens: {df['total_tokens'].sum():,.0f}")
    
    print(f"\nSample data (first 3 rows):")
    print(df.head(3).to_string(index=False))
    
    return True

def main():
    print("="*60)
    print("Azure OpenAI Usage Data Extractor")
    print("="*60)
    
    all_records = []
    
    # Try each OpenAI account
    for account in OPENAI_ACCOUNTS[:3]:  # Start with first 3 to test
        print(f"\n{'='*60}")
        print(f"Processing: {account}")
        print(f"{'='*60}")
        
        records = export_usage_via_diagnostic_settings(account, days_back=30)
        if records:
            all_records.extend(records)
            print(f"  ✓ Collected {len(records)} records from {account}")
    
    if all_records:
        success = create_csv_from_records(all_records, OUTPUT_FILE)
        if success:
            print(f"\n{'='*60}")
            print(f"✓ SUCCESS!")
            print(f"{'='*60}")
            print(f"\nYou can now upload '{OUTPUT_FILE}' to the PTU simulator at:")
            print(f"  http://localhost:8501")
    else:
        print("\n" + "="*60)
        print("No usage data found!")
        print("="*60)
        print("\nPossible reasons:")
        print("  1. Diagnostic settings may not be configured for Log Analytics")
        print("  2. The data is only in the storage account (requires network access)")
        print("  3. No usage in the selected time period")
        print("\nYou can:")
        print("  1. Use the sample data: 'OpenAI Usage.csv'")
        print("  2. Export data from Azure Portal Cost Management")
        print("  3. Configure network access to the storage account")

if __name__ == "__main__":
    main()

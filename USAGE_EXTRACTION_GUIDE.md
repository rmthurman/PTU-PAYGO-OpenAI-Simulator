# Azure OpenAI Usage Data Extraction Guide

This guide explains how to extract Azure OpenAI usage data from Azure Storage diagnostic logs for use with the PTU vs PAYGO Traffic Simulator.

## Prerequisites

1. **Azure CLI** - Must be logged in with `az login`
2. **Azure Permissions** - Need "Storage Blob Data Reader" role on the storage account
3. **Python Environment** - Python 3.11+ with required packages (already installed)

## Quick Start

### 1. List Available OpenAI Accounts

See which OpenAI accounts have logs in your storage:

```bash
python extract_azure_usage.py --list-accounts
```

### 2. Extract Last 7 Days (Default)

Extract the most recent 7 days of data:

```bash
python extract_azure_usage.py
```

This creates `azure_openai_usage.csv` with data from all OpenAI accounts.

### 3. Extract Custom Date Range

Extract data for a specific date range:

```bash
python extract_azure_usage.py --start-date 2025-11-01 --end-date 2025-11-13
```

### 4. Extract Last N Days

Extract the last 30 days:

```bash
python extract_azure_usage.py --days 30
```

### 5. Filter by Specific Accounts

Extract only from specific OpenAI accounts:

```bash
python extract_azure_usage.py --days 30 --accounts RANDYSOPENAIEASTUS RANDYSOPENAIWESTUS3
```

### 6. Include Metadata

Include additional columns (model, location, duration, etc.):

```bash
python extract_azure_usage.py --days 7 --include-metadata
```

### 7. Custom Output File

Specify a different output file name:

```bash
python extract_azure_usage.py --days 30 --output my_usage_data.csv
```

## Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--list-accounts` | List all OpenAI accounts and exit | `--list-accounts` |
| `--start-date` | Start date (YYYY-MM-DD) | `--start-date 2025-10-01` |
| `--end-date` | End date (YYYY-MM-DD) | `--end-date 2025-11-13` |
| `--days` | Days to look back (default: 7) | `--days 30` |
| `--accounts` | Specific account names | `--accounts account1 account2` |
| `--output` | Output file name | `--output usage.csv` |
| `--include-metadata` | Include extra columns | `--include-metadata` |
| `--max-blobs` | Limit blobs processed | `--max-blobs 100` |
| `--storage-account` | Storage account name | `--storage-account myaccount` |

## Example Workflows

### Scenario 1: Monthly Analysis

Extract a full month of data for analysis:

```bash
python extract_azure_usage.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --output october_usage.csv \
  --include-metadata
```

### Scenario 2: Compare Regions

Extract and compare usage from different regions:

```bash
# East US
python extract_azure_usage.py \
  --days 30 \
  --accounts RANDYSOPENAIEASTUS \
  --output eastus_usage.csv

# West US 3
python extract_azure_usage.py \
  --days 30 \
  --accounts RANDYSOPENAIWESTUS3 \
  --output westus3_usage.csv
```

### Scenario 3: Quick Test

Test with limited data:

```bash
python extract_azure_usage.py \
  --days 7 \
  --max-blobs 10 \
  --output test_usage.csv
```

## Output Format

The generated CSV file contains:

### Standard Columns (for PTU Simulator)
- `timestamp [UTC]` - Request timestamp
- `input_tokens` - Estimated input tokens
- `output_tokens` - Estimated output tokens  
- `total_tokens` - Total token count

### Metadata Columns (with --include-metadata)
- `operation` - API operation (ChatCompletions_Create, Embeddings_Create)
- `model` - Model name (gpt-4o, text-embedding-3-large, etc.)
- `deployment` - Deployment name
- `location` - Azure region
- `duration_ms` - Request duration in milliseconds
- `stream_type` - Streaming or Non-Streaming
- `request_bytes` - Request size in bytes
- `response_bytes` - Response size in bytes

## Important Notes

### Token Count Estimation

⚠️ **Token counts are estimated** from request/response byte sizes using the approximation:
- Roughly 4 bytes per token
- For embeddings, output tokens are set to 0

For production analysis, consider using:
- Azure Monitor Log Analytics queries
- Direct API response parsing
- Azure OpenAI metrics endpoints

### Storage Account Access

The script requires:
1. **Azure AD Authentication** - Uses `DefaultAzureCredential`
2. **RBAC Permissions** - "Storage Blob Data Reader" role
3. **Network Access** - Public access or private endpoint connectivity

If you get authorization errors:
```bash
# Assign the role (if you have permissions)
az role assignment create \
  --role "Storage Blob Data Reader" \
  --assignee YOUR_USER_ID \
  --scope /subscriptions/SUB_ID/resourceGroups/RG_NAME/providers/Microsoft.Storage/storageAccounts/ACCOUNT_NAME
```

### Data Source

The script reads from:
- **Container**: `insights-logs-requestresponse`
- **Log Type**: Azure Diagnostic Logs
- **Format**: JSON Lines (one JSON object per line)

This requires diagnostic settings to be configured on your OpenAI accounts to send logs to the storage account.

## Using with PTU Simulator

After extracting data:

1. **Start the simulator**:
   ```bash
   streamlit run app.py
   ```

2. **Open browser**: http://localhost:8501

3. **Upload your CSV file** (e.g., `azure_openai_usage.csv`)

4. **Configure PTU settings**:
   - Select model
   - Choose pricing scheme
   - Set PTU capacity
   - Apply discounts

5. **Analyze results** to compare PTU vs PAYGO costs

## Troubleshooting

### "AuthorizationFailure" Error

**Problem**: No permission to access storage account

**Solution**:
```bash
# Check current role assignments
az role assignment list --scope /subscriptions/.../storageAccounts/ACCOUNT_NAME

# Assign reader role
az role assignment create --role "Storage Blob Data Reader" --assignee YOUR_EMAIL --scope /subscriptions/.../storageAccounts/ACCOUNT_NAME
```

### "Network Rules" Error

**Problem**: Storage account has network restrictions

**Solution**:
```bash
# Temporarily enable public access
az storage account update \
  -n ACCOUNT_NAME \
  -g RESOURCE_GROUP \
  --public-network-access Enabled \
  --default-action Allow

# After extraction, restore restrictions
az storage account update \
  -n ACCOUNT_NAME \
  -g RESOURCE_GROUP \
  --public-network-access Disabled \
  --default-action Deny
```

### No Data Found

**Possible causes**:
1. No logs in the date range
2. Diagnostic settings not configured
3. Wrong storage account or container
4. Account name filter too restrictive

**Solution**:
```bash
# List accounts to verify
python extract_azure_usage.py --list-accounts

# Check diagnostic settings
az monitor diagnostic-settings list --resource OPENAI_RESOURCE_ID

# Try broader date range
python extract_azure_usage.py --days 90
```

## Advanced Usage

### Custom Storage Account

If using a different storage account:

```bash
python extract_azure_usage.py \
  --storage-account mystorageaccount \
  --days 30
```

### Batch Processing

Process multiple accounts separately:

```bash
for account in ACCOUNT1 ACCOUNT2 ACCOUNT3; do
  python extract_azure_usage.py \
    --days 30 \
    --accounts $account \
    --output ${account}_usage.csv
done
```

### Combine Multiple Extractions

```python
import pandas as pd

# Read multiple CSVs
df1 = pd.read_csv('october_usage.csv')
df2 = pd.read_csv('november_usage.csv')

# Combine and deduplicate
combined = pd.concat([df1, df2]).drop_duplicates()

# Save
combined.to_csv('combined_usage.csv', index=False)
```

## Support

For issues or questions:
1. Check the error message and troubleshooting section
2. Verify Azure permissions and network access
3. Review diagnostic settings configuration
4. Check the storage account logs container

## See Also

- [PTU-PAYGO-OpenAI-Simulator README](README.md)
- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure Storage Documentation](https://learn.microsoft.com/azure/storage/)

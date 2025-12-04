# Azure OpenAI Logs Analysis - Setup & Usage Guide

## Prerequisites

1. **Python 3.7+**
2. **Azure Storage Account Access**
   - Storage account: `nvstrgitentint`
   - Container: `insights-logs-requestresponse`
   - Access credentials (connection string or account key)

## Installation

### Step 1: Install Required Packages

```bash
# Install Azure Storage SDK
pip install azure-storage-blob

# Or install all requirements
pip install -r requirements.txt
```

### Step 2: Get Azure Storage Credentials

#### Option A: Connection String (Recommended)
1. Go to Azure Portal
2. Navigate to Storage Account: `nvstrgitentint`
3. Go to **Security + networking** → **Access keys**
4. Copy **Connection string** from key1 or key2

#### Option B: Account Key
1. Same as above
2. Copy **Key** instead of connection string

## Usage

### Quick Start (Using Environment Variable)

```bash
# Set connection string as environment variable
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=nvstrgitentint;AccountKey=...;EndpointSuffix=core.windows.net"

# Run the analysis
python3 download_azure_logs.py

# Output will be in: ./analysis_output/azure_logs_analysis.csv
```

### With Command Line Arguments

```bash
# Using connection string
python3 download_azure_logs.py \
  --connection-string "DefaultEndpointsProtocol=https;AccountName=nvstrgitentint;..." \
  --output complete_analysis.csv

# Using account key
python3 download_azure_logs.py \
  --storage-account nvstrgitentint \
  --account-key "your-account-key-here" \
  --output complete_analysis.csv

# Specify different container
python3 download_azure_logs.py \
  --container insights-logs-requestresponse \
  --output analysis.csv
```

### Advanced Options

```bash
python3 download_azure_logs.py \
  --storage-account nvstrgitentint \
  --container insights-logs-requestresponse \
  --output-dir ./my_reports \
  --output ptu_data.csv \
  --account-key "your-key"
```

## What Gets Generated

### 1. CSV File (`azure_logs_analysis.csv`)
Ready to upload to PTU Calculator:
```csv
timestamp [UTC],input_tokens,output_tokens,total_tokens
"8/15/2025, 5:12:14.121000 PM",3396,1230,4626
"8/15/2025, 5:50:43.282000 PM",3602,1480,5082
```

### 2. Analysis Report (`azure_logs_analysis_report.txt`)
Detailed statistics including:
- Total requests processed
- Token usage summary (estimated)
- Model distribution
- Error codes and failures
- Time range and duration
- Monthly projections
- Warnings about data quality

## Expected Output

```
================================================================================
Azure OpenAI Logs Analyzer
================================================================================
Storage Account: nvstrgitentint
Container: insights-logs-requestresponse
Output: ./analysis_output/azure_logs_analysis.csv
Using connection string from environment variable
✅ Connected to Azure Storage

📦 Processing container: insights-logs-requestresponse
Found 1,234 blobs in container
Processing blob 1234/1234: resourceId=.../y=2025/m=08/d=15/h=17/m=00/PT1H.json
✅ Processed 1,234 blobs successfully

📝 Writing CSV to: ./analysis_output/azure_logs_analysis.csv
✅ Wrote 45,678 rows to CSV

📊 Generating report: ./analysis_output/azure_logs_analysis_report.txt
✅ Report generated

================================================================================
✅ ANALYSIS COMPLETE
================================================================================
CSV File: ./analysis_output/azure_logs_analysis.csv
Report: ./analysis_output/azure_logs_analysis_report.txt

Processed: 45,678 successful requests
Total tokens (estimated): 123,456,789

📊 Upload azure_logs_analysis.csv to the PTU Calculator app!
```

## Troubleshooting

### Error: "Import azure.storage.blob could not be resolved"

```bash
pip install azure-storage-blob
```

### Error: "No authentication provided"

You need to provide credentials using one of these methods:

```bash
# Method 1: Environment variable
export AZURE_STORAGE_CONNECTION_STRING="..."
python3 download_azure_logs.py

# Method 2: Command line
python3 download_azure_logs.py --connection-string "..."

# Method 3: Account key
python3 download_azure_logs.py --account-key "..."
```

### Error: "Container not found" or "Authentication failed"

Check:
1. Storage account name is correct: `nvstrgitentint`
2. Container name is correct: `insights-logs-requestresponse`
3. Credentials are valid and not expired
4. You have read permissions on the container

### Warning: "No valid token data found"

This means:
- Container might be empty
- All requests failed (non-200 status codes)
- Wrong container selected

Try:
```bash
# List available containers
python3 -c "from azure.storage.blob import BlobServiceClient; \
  client = BlobServiceClient.from_connection_string('your-connection-string'); \
  [print(c.name) for c in client.list_containers()]"
```

## Security Best Practices

1. **Never commit credentials to git**
   ```bash
   # Add to .gitignore
   echo "*.key" >> .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment variables**
   ```bash
   # Create .env file (add to .gitignore!)
   echo 'AZURE_STORAGE_CONNECTION_STRING="..."' > .env
   
   # Load in terminal
   source .env
   ```

3. **Use Azure Key Vault for production**
   ```bash
   # Store in Key Vault instead of local files
   az keyvault secret set --vault-name mykeyvault --name storage-connection --value "..."
   ```

## Next Steps After Analysis

1. ✅ Review the generated report
2. ✅ Upload CSV to PTU Calculator: `streamlit run app.py`
3. ⚠️ Remember: Token counts are ESTIMATES (±25-30%)
4. ✅ Add 1.3-1.5x safety buffer to PTU calculations
5. 📊 Implement application logging for accurate data collection
6. 🎯 Re-run analysis with real token data before final PTU commitment

## Files Created

- `download_azure_logs.py` - Main analysis script
- `analysis_output/azure_logs_analysis.csv` - PTU Calculator input
- `analysis_output/azure_logs_analysis_report.txt` - Detailed report

## Support

Common issues:
- **Slow processing**: Large containers may take 10-30 minutes
- **Memory errors**: Process in batches if needed
- **Rate limiting**: Script includes error handling and retries
- **Partial data**: Failed blobs are skipped, check report for counts

For more information, see:
- `GET_REAL_TOKEN_DATA.md` - How to get accurate token counts
- `QUICK_REFERENCE.md` - Quick command reference
- `README_AZURE_LOGS.md` - Understanding Azure log types

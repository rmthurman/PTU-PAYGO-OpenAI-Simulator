# Complete Azure Analysis - Quick Guide

## 🎯 Goal
Analyze ALL logs from Azure Storage Account `nvstrgitentint` to determine PTU vs PAYGO pricing.

## 📋 What You Need

1. **Azure Storage Connection String**
   - Storage Account: `nvstrgitentint`
   - Container: `insights-logs-requestresponse`
   - Get from: Azure Portal → Storage Account → Access Keys

2. **Python 3.7+** (already installed ✅)

3. **Azure Storage SDK** (automatically installed)

## 🚀 Three Ways to Run

### Option 1: Quick Start Script (Easiest)

```bash
./analyze_azure_logs.sh
```

This will:
- Prompt for connection string if needed
- Install dependencies automatically
- Process all logs
- Generate report
- Create CSV ready for PTU Calculator

### Option 2: Manual with Environment Variable

```bash
# Set connection string (do this once per terminal session)
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=nvstrgitentint;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net"

# Run analysis
python3 download_azure_logs.py

# View results
cat analysis_output/azure_logs_analysis_report.txt
```

### Option 3: Manual with Command Line

```bash
python3 download_azure_logs.py \
  --storage-account nvstrgitentint \
  --connection-string "YOUR_CONNECTION_STRING_HERE" \
  --output complete_ptu_analysis.csv
```

## 📊 What Gets Created

After running, you'll get:

### 1. CSV File for PTU Calculator
**Location:** `./analysis_output/azure_logs_analysis.csv`

```csv
timestamp [UTC],input_tokens,output_tokens,total_tokens
"8/15/2025, 5:12:14.121000 PM",3396,1230,4626
"8/15/2025, 5:50:43.282000 PM",3602,1480,5082
...
```

### 2. Detailed Analysis Report
**Location:** `./analysis_output/azure_logs_analysis_report.txt`

Contains:
- ✅ Total requests processed
- ✅ Token usage statistics (estimated)
- ✅ Model distribution
- ✅ Error rates and codes
- ✅ Time range analysis
- ✅ Monthly projections
- ⚠️ Data quality warnings

## 🔍 Example Report Output

```
================================================================================
Azure OpenAI Logs Analysis Report
================================================================================

OVERALL STATISTICS
--------------------------------------------------------------------------------
Total log entries processed: 125,834
Successful requests (200): 123,456
Failed requests: 2,378
Blobs processed: 1,247
Blobs failed: 3

ERROR CODES
--------------------------------------------------------------------------------
  408: 1,234 requests (timeout)
  429: 891 requests (rate limit)
  500: 253 requests (server error)

MODELS USED
--------------------------------------------------------------------------------
  gpt-4o: 87,654 requests
  gpt-4: 23,456 requests
  gpt-35-turbo: 12,346 requests

TOKEN STATISTICS (ESTIMATED)
--------------------------------------------------------------------------------
Total input tokens: 456,789,123
Total output tokens: 123,456,789
Total tokens: 580,245,912
Average tokens per request: 4,700
Average input per request: 3,700
Average output per request: 1,000

TIME RANGE
--------------------------------------------------------------------------------
First request: 2025-08-01 08:15:23
Last request: 2025-08-31 23:45:12
Duration: 30.6 days

MONTHLY PROJECTION
--------------------------------------------------------------------------------
Projected monthly tokens: 569,234,567
Projected monthly requests: 121,098
```

## ⚠️ Important Warnings

### Token Counts are ESTIMATES
- Based on byte length, NOT actual tokens
- Accuracy: ±25-30% error margin
- Formula: bytes / 3.5 chars per token

### For Production PTU Planning
1. ✅ Use this analysis for initial assessment
2. ✅ Add 1.3-1.5x safety buffer to calculations
3. ⚠️ Collect real token data from API responses
4. ⚠️ Re-analyze with actual tokens before committing

See `GET_REAL_TOKEN_DATA.md` for how to collect accurate data.

## 📈 Next Steps

### 1. Upload to PTU Calculator
```bash
streamlit run app.py
```
Then upload: `analysis_output/azure_logs_analysis.csv`

### 2. Review Analysis
The PTU Calculator will show:
- Peak tokens per minute (TPM)
- Optimal PTU configuration
- Cost comparison: PTU vs PAYGO
- Traffic optimization recommendations

### 3. Make Informed Decision
Based on the analysis:
- Determine if PTU makes financial sense
- Calculate required PTU units for your peak load
- Plan for capacity buffer (recommend 1.5x peak)
- Consider implementing real token logging

## 🔧 Troubleshooting

### "Module 'azure.storage.blob' not found"
```bash
pip3 install azure-storage-blob
```

### "Authentication failed"
- Check connection string is complete
- Verify you have read permissions
- Ensure storage account name is correct: `nvstrgitentint`

### "No valid token data found"
- Container might be empty
- Check container name: `insights-logs-requestresponse`
- Verify logs exist in the time period

### Script is slow
- Normal for large datasets (10-30 minutes)
- Progress shown per blob
- Can interrupt with Ctrl+C and resume

## 📁 Files in This Project

### Main Scripts
- `download_azure_logs.py` - Main analysis tool
- `analyze_azure_logs.sh` - Quick start wrapper
- `convert_azure_logs.py` - Single file converter

### Documentation
- `SETUP_AZURE_ANALYSIS.md` - Detailed setup guide
- `GET_REAL_TOKEN_DATA.md` - How to get accurate tokens
- `QUICK_REFERENCE.md` - Command cheat sheet
- `README_AZURE_LOGS.md` - Understanding Azure logs

### PTU Calculator App
- `app.py` - Streamlit web interface
- `data_processing.py` - CSV processing
- `ptu_calculations.py` - PTU analysis engine
- `pricing.py` - Pricing models

## 🎓 Understanding the Results

### Peak TPM is Critical
PTU pricing is based on capacity (tokens per minute), not usage.
- Your peak TPM determines minimum PTU units needed
- Bursts above PTU capacity spill to PAYGO
- Right-size PTU to handle ~80-90% of traffic

### Cost Optimization
The calculator will show you:
1. **Pure PAYGO** - Baseline cost
2. **Pure PTU** - Fixed cost + capacity
3. **Hybrid** - PTU for base + PAYGO for bursts

Optimal is usually hybrid approach.

## 💡 Pro Tips

1. **Analyze multiple time periods**
   - Include peak business hours
   - Cover month-end spikes
   - Capture seasonal variations

2. **Don't forget about failed requests**
   - 408/429 errors still consume capacity
   - Plan for retries in your TPM calculations

3. **Model-specific considerations**
   - Different models have different TPM/PTU ratios
   - GPT-4 typically: 3,000 TPM per PTU
   - GPT-3.5 typically: 10,000 TPM per PTU

4. **Safety buffers matter**
   - Estimates: Add 1.3-1.5x buffer
   - Real data: Add 1.2x buffer
   - Growth planning: Add 2x buffer

## 🚀 Let's Get Started!

**Ready to analyze?**

```bash
# Quick start (recommended)
./analyze_azure_logs.sh

# Or set connection string and run
export AZURE_STORAGE_CONNECTION_STRING="..."
python3 download_azure_logs.py
```

The analysis will take 10-30 minutes depending on log volume. 
You'll get a complete report with everything needed for PTU planning!

---

**Questions?** Check the documentation files or review the code comments.

**Need accurate data?** See `GET_REAL_TOKEN_DATA.md` for implementation guide.

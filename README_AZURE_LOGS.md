# Converting Azure OpenAI Diagnostic Logs for PTU Calculator

## Overview

This guide explains how to convert Azure OpenAI diagnostic logs into the CSV format expected by the PTU Calculator app.

## Important Limitations ⚠️

**Azure diagnostic logs do NOT contain actual token counts**. The conversion script estimates tokens based on:
- `requestLength` (bytes) → estimated input tokens
- `responseLength` (bytes) → estimated output tokens
- Using rough approximation: ~4 characters per token

### For Accurate Analysis, You Need:

1. **Azure OpenAI Usage Logs** - These contain actual token counts
2. **Application logs** that capture the actual token usage from API responses
3. **OpenAI API response data** with `usage.prompt_tokens` and `usage.completion_tokens`

## Azure Log Types

### 1. Diagnostic Logs (What you have: `PT1H.json`)
- ❌ Contains: API call metadata, duration, status codes
- ❌ Does NOT contain: Actual token counts
- ⚠️ Only provides rough estimates

### 2. Usage Logs (What you need)
- ✅ Contains: Actual token consumption per request
- ✅ Includes: prompt_tokens, completion_tokens, total_tokens
- ✅ Required for: Accurate PTU vs PAYGO analysis

## Getting Better Data from Azure

### Option 1: Export Usage Data from Azure Portal

1. Go to Azure Portal → Your OpenAI Resource
2. Navigate to **Monitoring** → **Metrics**
3. Select metric: **Tokens Generated** or **Token Usage**
4. Export data with timestamp and token counts

### Option 2: Use Azure Monitor Logs (KQL Query)

```kql
AzureDiagnostics
| where Category == "RequestResponse"
| where OperationName == "ChatCompletions_Create"
| where ResultSignature == "200"
| extend Properties = parse_json(properties_s)
| project 
    TimeGenerated,
    ModelName = tostring(Properties.modelName),
    ModelVersion = tostring(Properties.modelVersion),
    StreamType = tostring(Properties.streamType)
| order by TimeGenerated asc
```

### Option 3: Capture from Application

If your application calls Azure OpenAI API, capture the response:

```python
response = client.chat.completions.create(...)
tokens_used = {
    'timestamp': datetime.utcnow(),
    'prompt_tokens': response.usage.prompt_tokens,
    'completion_tokens': response.usage.completion_tokens,
    'total_tokens': response.usage.total_tokens
}
# Log this data for later analysis
```

## Using the Conversion Script

If you only have diagnostic logs (with rough estimates):

```bash
python3 convert_azure_logs.py sample/PT1H.json sample/PT1H_converted.csv
```

### Expected Input Format

The script handles:
- Single JSON object: `{ "time": "...", "operationName": "..." }`
- Array of objects: `[{...}, {...}]`
- Newline-delimited JSON (NDJSON): One object per line

### Expected Output Format

CSV with columns:
```csv
timestamp [UTC],input_tokens,output_tokens,total_tokens
"8/18/2025, 12:00:38.941 AM",1345,69,1414
"8/18/2025, 12:00:41.959 AM",967,48,1015
```

## Creating Test Data

If you need to generate realistic test data, see `OpenAI Usage.csv` as an example of the proper format with actual token counts.

## Next Steps

1. ✅ Convert your diagnostic logs with `convert_azure_logs.py`
2. ⚠️ Note that estimates are rough approximations
3. 🎯 For production analysis, obtain actual usage logs with real token counts
4. 📊 Upload the CSV to the PTU Calculator app

## Questions?

- The diagnostic logs are from: Azure OpenAI Service diagnostic settings
- The expected format is: OpenAI API usage data with token counts
- For accurate PTU planning: Use actual token consumption data, not diagnostics

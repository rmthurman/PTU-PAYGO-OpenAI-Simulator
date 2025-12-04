# How to Get Actual Token Data from Azure OpenAI

## The Problem
Azure OpenAI diagnostic logs (`insights-logs-requestresponse`) contain:
- ✅ `requestLength` and `responseLength` (in bytes)
- ❌ NO actual token counts (prompt_tokens, completion_tokens)

## Solutions to Get Real Token Data

### Option 1: Enable Enhanced Logging (Recommended)

Azure OpenAI can be configured to log additional fields. Check your diagnostic settings:

1. Go to Azure Portal → Your OpenAI Resource
2. Navigate to **Monitoring** → **Diagnostic Settings**
3. Ensure these are enabled:
   - ✅ Request Response logs
   - ✅ Audit logs
4. Check if "Include full request/response" is enabled

### Option 2: Use Azure Monitor Logs with Extended Properties

Query your Log Analytics workspace for more detailed data:

```kql
// Query to check if token data is available
AzureDiagnostics
| where Category == "RequestResponse"
| where OperationName == "ChatCompletions_Create"
| where ResultSignature == "200"
| extend props = parse_json(properties_s)
| extend 
    ModelName = tostring(props.modelDeploymentName),
    RequestLength = toint(props.requestLength),
    ResponseLength = toint(props.responseLength),
    PromptTokens = toint(props.prompt_tokens),
    CompletionTokens = toint(props.completion_tokens),
    TotalTokens = toint(props.total_tokens)
| where isnotnull(TotalTokens) // Check if token data exists
| project 
    TimeGenerated,
    ModelName,
    PromptTokens,
    CompletionTokens,
    TotalTokens
| order by TimeGenerated asc
| take 10
```

Export results to CSV if token columns are populated.

### Option 3: Application-Level Logging (Most Reliable)

Capture token usage directly from your application:

#### Python Example:
```python
from openai import AzureOpenAI
import csv
from datetime import datetime

client = AzureOpenAI(
    api_key="your-key",
    api_version="2024-02-01",
    azure_endpoint="https://your-resource.openai.azure.com"
)

# Open CSV file for logging
with open('token_usage.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens'])
    
    # Make API call
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    
    # Log token usage
    timestamp = datetime.utcnow().strftime("%-m/%-d/%Y, %-I:%M:%S.%f %p")
    usage = response.usage
    writer.writerow([
        timestamp,
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens
    ])
    
    print(f"Tokens used: {usage.total_tokens}")
```

#### JavaScript/TypeScript Example:
```javascript
import { AzureOpenAI } from "openai";
import * as fs from "fs";

const client = new AzureOpenAI({
  apiKey: process.env.AZURE_OPENAI_API_KEY,
  apiVersion: "2024-02-01",
  endpoint: "https://your-resource.openai.azure.com"
});

// Create CSV writer
const csvStream = fs.createWriteStream('token_usage.csv');
csvStream.write('timestamp [UTC],input_tokens,output_tokens,total_tokens\n');

const response = await client.chat.completions.create({
  model: "gpt-4",
  messages: [{ role: "user", content: "Hello!" }]
});

// Log token usage
const timestamp = new Date().toLocaleString('en-US', { 
  timeZone: 'UTC',
  month: 'numeric',
  day: 'numeric', 
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
  fractionalSecondDigits: 3,
  hour12: true
});

csvStream.write(`"${timestamp}",${response.usage.prompt_tokens},${response.usage.completion_tokens},${response.usage.total_tokens}\n`);
console.log(`Tokens used: ${response.usage.total_tokens}`);
```

### Option 4: Azure Cost Management Export

1. Go to **Cost Management + Billing**
2. Navigate to **Exports**
3. Create export for Azure OpenAI resource
4. Export will include:
   - Service name: "Azure OpenAI"
   - Meter name: "Tokens"
   - Quantity: Token count
   - Date/Time

Note: This is aggregated billing data, not per-request granularity.

### Option 5: Use Application Insights

If your application uses Application Insights:

```csharp
// C# with Application Insights
var telemetryClient = new TelemetryClient();

var response = await client.GetChatCompletionsAsync(deployment, messages);

// Log custom metric
telemetryClient.TrackMetric(
    "TokensUsed",
    response.Value.Usage.TotalTokens,
    new Dictionary<string, string>
    {
        { "PromptTokens", response.Value.Usage.PromptTokens.ToString() },
        { "CompletionTokens", response.Value.Usage.CompletionTokens.ToString() },
        { "Model", deployment }
    }
);
```

Query Application Insights for token metrics.

## Which Option Should You Use?

| Option | Accuracy | Granularity | Effort | Best For |
|--------|----------|-------------|---------|----------|
| Enhanced Logging | ⭐⭐⭐ | Per-request | Low | If supported by Azure |
| Log Analytics | ⭐⭐⭐ | Per-request | Low | Checking existing logs |
| Application Logging | ⭐⭐⭐⭐⭐ | Per-request | Medium | Production apps |
| Cost Management | ⭐⭐ | Daily aggregate | Low | Rough estimates |
| App Insights | ⭐⭐⭐⭐⭐ | Per-request | Medium | .NET/Enterprise apps |

## Recommended Approach

**For accurate PTU planning:**

1. ✅ Implement application-level token logging (Option 3)
2. ✅ Collect at least 7-30 days of production traffic data
3. ✅ Include peak usage periods (business hours, month-end, etc.)
4. ✅ Use the actual token counts from API responses

**For quick analysis with current data:**

1. ⚠️ Use the conversion script with `insights-logs-requestresponse`
2. ⚠️ Understand that token counts are estimates (~25-30% error margin)
3. ⚠️ Add a safety buffer (1.3-1.5x) to your PTU calculations
4. ✅ Plan to collect real data for final sizing decisions

## Converting Your Current Logs

```bash
# Convert Azure diagnostic logs (with estimates)
python3 convert_azure_logs.py sample/PT1H-2.json sample/PT1H-2_converted.csv

# The script will warn you about data quality
# Use the CSV for initial analysis, but plan to get real token data
```

## Next Steps

1. Determine which option works best for your setup
2. Start collecting real token usage data
3. Run PTU calculator with both estimated and real data
4. Compare results to validate estimates
5. Make final PTU decisions based on real data

---

**Remember:** PTU commitments are typically annual contracts. It's worth spending a few days to get accurate token data rather than relying on estimates that could be off by 25-30%.

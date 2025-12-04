# 🚀 PTU vs PAYGO Traffic Simulator

**A comprehensive Azure OpenAI cost analysis tool for comparing Provisioned Throughput Units (PTU) vs Pay-as-you-go (PAYGO) pricing**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.49+-red.svg)](https://streamlit.io/)
[![Azure](https://img.shields.io/badge/Azure-OpenAI-0078D4.svg)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📊 Overview

The PTU vs PAYGO Traffic Simulator helps you make data-driven decisions about Azure OpenAI pricing models by analyzing your actual usage patterns. Upload your usage CSV or analyze Azure Storage logs directly to get detailed insights into:

- **Cost Analysis**: Compare PTU vs PAYGO pricing across different configurations
- **Traffic Optimization**: Find the optimal PTU count for your workload patterns  
- **Token Distribution**: Understand how your tokens would be allocated between PTU and PAYGO
- **Utilization Metrics**: Analyze PTU capacity utilization over time
- **Azure Log Analysis**: Process diagnostic logs directly from Azure Storage

## ✨ Key Features

### 🎯 **Smart Configuration**
- **6 PTU Pricing Schemes**: Monthly/Yearly Reservation, Hourly Global/Data Zone/Regional, Monthly Commitment
- **Flexible Discount Support**: Apply custom discount percentages to PTU pricing
- **Model Selection**: Pre-configured for GPT-4.1 with 3,000 TPM capacity
- **Regional Deployment Options**: Compare Global vs Regional pricing

### 📈 **Advanced Analytics**
- **Per-minute Utilization**: More accurate than peak-based calculations
- **Token Weighting**: Accounts for input/output token pricing ratios (e.g., 1:4 for PTU capacity)
- **Spillover Analysis**: Shows how excess tokens flow to PAYGO when PTU capacity is exceeded
- **Cost Projection**: Annualize costs based on dataset duration

### 🎨 **Interactive Visualizations**
- **Real-time Cost Charts**: Compare PTU vs PAYGO costs across configurations
- **Token Distribution Charts**: Visualize how tokens are handled by each pricing model
- **Traffic Optimization Insights**: Get recommendations with color-coded cost indicators

### 📊 **Comprehensive Reporting**
- **Detailed Results Table**: US-formatted numbers with comma separators
- **Traffic Optimization Metrics**: Shows percentage of tokens optimized by PTU
- **CSV Export**: Download complete analysis results
- **Performance Metrics**: Dataset overview with peak/average TPM statistics

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- OpenAI usage CSV file with columns: `timestamp`, `input tokens`, `output tokens`

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/karpikpl/PTU-PAYGO-OpenAI-Simulator.git
   cd PTU-PAYGO-OpenAI-Simulator
   ```

2. **Install dependencies** (using uv - recommended)
   ```bash
   uv sync
   ```

3. **Run the application**
   ```bash
   uv run streamlit run app.py
   ```

4. **Open your browser** to `http://localhost:8501`

---

## 📸 Screenshots

### 🏠 Main Dashboard
![Main Dashboard](screenshots/input.png)
*Configure PTU pricing, model selection, and upload your usage data*

### 📊 Dataset Overview
![Dataset Overview](screenshots/dataset_overview.png)
*Analyze your token usage patterns with key metrics and statistics*

### 📈 PTU Analysis Results
![PTU Analysis Results](screenshots/results.png)
*Comprehensive comparison table with formatted numbers and percentage breakdowns*

### 🎯 Traffic Optimization
![Traffic Optimization](screenshots/traffic_optimization.png)
*Smart recommendations with color-coded cost indicators (🟠 more expensive, 🟢 cost savings)*

### 📉 Cost Analysis Charts
![Cost Analysis Charts](screenshots/results.png)
*Interactive visualizations showing cost trends and token distribution*

---

## 🔧 Usage Guide

### Option 1: Analyze Azure Storage Logs (Recommended for Azure Customers)

**Quick Start - Automated Analysis**
```bash
# Interactive script - will prompt for connection string
./analyze_azure_logs.sh
```

**Manual Analysis**
```bash
# Set your Azure Storage connection string
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=nvstrgitentint;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net"

# Run the analyzer
python3 download_azure_logs.py --storage-account nvstrgitentint --container insights-logs-requestresponse

# Results will be in: ./analysis_output/azure_logs_analysis.csv
```

**Getting Your Connection String:**
1. Go to Azure Portal
2. Navigate to your Storage Account (e.g., `nvstrgitentint`)
3. Go to **Security + networking** → **Access keys**
4. Copy **Connection string** from key1 or key2

**⚠️ Important: Azure Logs Limitations**
- Azure diagnostic logs contain `requestLength` and `responseLength` (bytes), NOT actual token counts
- Token values are **ESTIMATES** based on ~3.5 characters per token
- Accuracy: ±25-30% error margin
- For production PTU planning, add 1.3-1.5x safety buffer
- See "Getting Accurate Token Data" section below for production recommendations

### Option 2: Upload Pre-processed CSV

**1. Configure Pricing**
- Select your preferred PTU pricing scheme (Monthly/Yearly/Hourly)
- Choose deployment preference (Global vs Regional)
- Apply any discounts you've negotiated
- Set PTU capacity (default: 3,000 TPM for GPT-4.1)

**2. Upload Usage Data**
Your CSV should include these columns (case-insensitive):
- `timestamp [UTC]` - Format: `8/18/2025, 12:00:38.941 AM`
- `input tokens` - Number of input tokens
- `output tokens` - Number of output tokens
- `total tokens` - Total tokens (optional, will be calculated)

**3. Analyze Results**
- **Dataset Overview**: Review your usage patterns and peak metrics
- **PTU Analysis**: Examine cost breakdowns across different PTU configurations
- **Traffic Optimization**: Get recommendations for optimal PTU count
- **Export Results**: Download detailed analysis as CSV

### Option 3: Convert Single Azure Log Files

```bash
# Convert individual JSON log files
python3 convert_azure_logs.py sample/PT1H.json output.csv

# Upload output.csv to the PTU Calculator web interface
```

---

## 📦 Azure Storage Containers

Azure OpenAI logs are stored in different containers:

| Container | Contains | Has Token Counts? | Use For |
|-----------|----------|-------------------|---------|
| `insights-logs-requestresponse` | Request/response metadata | ❌ No (estimates only) | This tool |
| `insights-logs-audit` | Admin operations | ❌ No | Not useful |
| `insights-logs-auditevent` | Security events | ❌ No | Not useful |
| `insights-metrics-pt1m` | Aggregated metrics | ⚠️ Totals only | Trends |

**Why No Token Counts in Azure Logs?**
- Azure diagnostic logs are metadata-only by design
- They contain byte lengths (`requestLength`, `responseLength`) but not token counts
- Token usage is tracked separately in Azure billing
- Actual tokens are in API responses (not logged retroactively)

---

## 🎯 Getting Accurate Token Data (Production Recommendations)

For production PTU planning, collect **actual token counts** from API responses:

### Python Example
```python
from openai import AzureOpenAI
import csv
from datetime import datetime

client = AzureOpenAI(api_key="...", api_version="2024-02-01", azure_endpoint="...")

with open('real_token_usage.csv', 'a', newline='') as f:
    writer = csv.writer(f)
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Your prompt"}]
    )
    
    # Capture actual token data from response
    timestamp = datetime.utcnow().strftime("%-m/%-d/%Y, %-I:%M:%S.%f %p")
    writer.writerow([
        timestamp,
        response.usage.prompt_tokens,      # ✅ Real count
        response.usage.completion_tokens,  # ✅ Real count
        response.usage.total_tokens        # ✅ Real count
    ])
```

### JavaScript/TypeScript Example
```javascript
import { AzureOpenAI } from "openai";
import * as fs from "fs";

const client = new AzureOpenAI({...});
const csvStream = fs.createWriteStream('token_usage.csv', {flags: 'a'});

const response = await client.chat.completions.create({...});

const timestamp = new Date().toLocaleString('en-US', {timeZone: 'UTC', ...});
csvStream.write(`"${timestamp}",${response.usage.prompt_tokens},${response.usage.completion_tokens},${response.usage.total_tokens}\n`);
```

### Alternative: Azure Monitor KQL Query
```kql
AzureDiagnostics
| where Category == "RequestResponse"
| where OperationName == "ChatCompletions_Create"
| where ResultSignature == "200"
| extend Properties = parse_json(properties_s)
| project 
    TimeGenerated,
    ModelName = tostring(Properties.modelDeploymentName),
    RequestLength = toint(Properties.requestLength),
    ResponseLength = toint(Properties.responseLength)
| order by TimeGenerated asc
```

---

## 🏗️ Architecture

### Modular Design
```
├── app.py                 # Main Streamlit application
├── data_processing.py     # CSV processing and data preparation
├── ptu_calculations.py    # PTU simulation and cost calculations
├── pricing.py             # Model pricing and configuration
└── utils.py              # Utility functions and formatting
```

### Key Algorithms

#### **PTU Simulation Engine**
- **Per-request Processing**: Simulates token allocation request by request
- **Minute-based Capacity**: Resets PTU capacity every minute (realistic behavior)
- **Proportional Spillover**: Maintains input/output ratios when PTU capacity is partially used
- **Output Token Weighting**: Accounts for different pricing weights (e.g., output tokens = 4x input tokens in PTU capacity)

#### **Cost Calculation**
- **Annualized Projections**: Scales costs based on dataset duration
- **Blended Pricing**: Combines PTU fixed costs with PAYGO variable costs
- **Regional Pricing Support**: Handles different pricing tiers and deployment options

---

## 🔬 Technical Details

### **Utilization Calculation**
The simulator uses **per-minute average utilization** rather than peak-based calculations:

```python
minute_utilizations = (tokens_per_minute / ptu_capacity_tpm * 100).clip(0, 100)
utilization_pct = minute_utilizations.mean()
```

This provides more accurate utilization metrics because PTU offers constant TPM capacity, and any minute with usage below capacity represents underutilization.

### **Token Weighting**
Different token types have different costs in PTU capacity:

```python
# Example: Input $0.002, Output $0.008 per 1K tokens
output_weight = output_price / input_price  # 4.0
request_ptu_demand = input_tokens + (output_tokens * output_weight)
```

### **Traffic Optimization Logic**
Finds PTU configurations closest to PAYGO cost (typically slightly more expensive) for balanced traffic optimization:

```python
# Prefer configurations slightly above PAYGO cost
above_paygo = configs[configs['cost_diff'] >= 0]
optimal_config = above_paygo.loc[above_paygo['cost_diff'].idxmin()]
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone and install in development mode
git clone https://github.com/karpikpl/PTU-PAYGO-OpenAI-Simulator.git
cd PTU-PAYGO-OpenAI-Simulator
uv sync --dev

# Run tests
uv run pytest

# Format code
uv run black .
uv run isort .
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI** for the PTU and PAYGO pricing models
- **Streamlit** for the excellent web framework
- **Pandas** for data processing capabilities

---

## �️ Available Tools

### `download_azure_logs.py` - Complete Azure Storage Analysis
Downloads and processes ALL logs from Azure Storage Account:
```bash
python3 download_azure_logs.py \
  --storage-account nvstrgitentint \
  --container insights-logs-requestresponse \
  --output complete_analysis.csv
```

### `convert_azure_logs.py` - Single File Converter
Converts individual Azure log JSON files to CSV:
```bash
python3 convert_azure_logs.py input.json output.csv
```

### `analyze_azure_logs.sh` - Quick Start Wrapper
Interactive script that handles everything:
```bash
./analyze_azure_logs.sh
```

---

## 📊 Understanding the Results

### Analysis Report Includes:
- **Overall Statistics**: Total requests, success/failure rates, blob processing
- **Error Codes**: Distribution of 408 (timeout), 429 (rate limit), 500 (server error), etc.
- **Models Used**: Breakdown by model deployment (gpt-4, gpt-4o, gpt-35-turbo, etc.)
- **Token Statistics**: Total and average tokens (estimated from byte lengths)
- **Time Range**: First/last request timestamps, duration in days
- **Monthly Projection**: Extrapolated monthly usage based on data duration

### Key Metrics:
- **Peak TPM**: Maximum tokens per minute (determines minimum PTU units)
- **Average TPM**: Mean tokens per minute across dataset
- **Utilization %**: How efficiently PTU capacity is used
- **Cost Optimization**: PTU configurations closest to PAYGO baseline

### Traffic Optimization:
The tool finds the optimal PTU configuration by:
1. Calculating pure PAYGO cost as baseline
2. Simulating different PTU counts (15-100 units)
3. Finding configuration closest to PAYGO cost (usually slightly more expensive)
4. Showing what % of tokens are handled by PTU vs spillover to PAYGO
5. Color-coding: 🟠 More expensive | 🟢 Cost savings

---

## ⚠️ Important Warnings & Best Practices

### Data Quality
- ✅ Azure logs provide: Timing, duration, model, response codes
- ❌ Azure logs DON'T have: Actual token counts
- 📊 Estimates based on: `bytes / 3.5 chars per token`
- 🎯 Error margin: ±25-30%

### Safety Buffers
| Data Source | Recommended Buffer | Use Case |
|-------------|-------------------|----------|
| Azure log estimates | 1.5x | Initial assessment |
| Real token data | 1.2x | Production sizing |
| With growth plan | 2.0x | Future-proofing |

### Production Checklist
- [ ] Collect 7-30 days of production traffic
- [ ] Include peak business hours and month-end spikes
- [ ] Capture actual token counts from API responses
- [ ] Account for retry logic and failed requests
- [ ] Consider model-specific TPM/PTU ratios
- [ ] Add appropriate safety buffer
- [ ] Validate assumptions with sample data

---

## 🔍 Troubleshooting

### Azure Storage Connection Issues
```
❌ "Authentication failed"
```
- Verify connection string is complete
- Check storage account name: `nvstrgitentint`
- Ensure you have read permissions
- Try regenerating access keys in Azure Portal

### Missing Dependencies
```
❌ "Module 'azure.storage.blob' not found"
```
```bash
pip3 install azure-storage-blob
```

### No Data Found
```
⚠️ "No valid token data found"
```
- Container might be empty
- Check container name: `insights-logs-requestresponse`
- Verify logs exist for the time period
- All requests may have failed (non-200 status)

### Slow Processing
- Normal for large datasets (10-30 minutes for full analysis)
- Progress shown per blob processed
- Can interrupt with Ctrl+C and resume
- Consider filtering by date range if needed

---

## �📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/karpikpl/PTU-PAYGO-OpenAI-Simulator/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/karpikpl/PTU-PAYGO-OpenAI-Simulator/discussions)
- 📧 **Azure Support**: For connection string or log access issues

---

## 🚀 Quick Command Reference

```bash
# Analyze all Azure logs (interactive)
./analyze_azure_logs.sh

# Analyze with environment variable
export AZURE_STORAGE_CONNECTION_STRING="..."
python3 download_azure_logs.py

# Convert single file
python3 convert_azure_logs.py input.json output.csv

# Run PTU Calculator web app
streamlit run app.py

# Install dependencies
pip3 install -r requirements.txt
# or
uv sync
```

---

<div align="center">
  <strong>Made with ❤️ for the Azure OpenAI community</strong>
  <br>
  <em>Optimize your AI costs with data-driven insights</em>
  <br><br>
  <sub>⚠️ Remember: Azure log estimates are for initial assessment only. Collect real token data for production PTU planning.</sub>
</div>

# Quick Reference: Azure Logs to PTU Calculator

## ✅ What You Have
- Azure container: `insights-logs-requestresponse`
- Format: Newline-delimited JSON (NDJSON)
- Contains: `requestLength`, `responseLength` (bytes only, NO actual tokens)

## 🔄 How to Convert

```bash
# Convert NDJSON logs to CSV
python3 convert_azure_logs.py sample/PT1H-2.json output.csv
```

## ⚠️ Important Warnings

| Issue | Impact | Solution |
|-------|--------|----------|
| Token counts are ESTIMATES | ±25-30% error | Collect real token data from API responses |
| Based on byte length | Not accurate for all models | Use application logging |
| Missing streaming data | Underestimates real usage | Enable complete logging |

## 📊 Estimation Formula Used

```
Input Tokens  = (requestLength - 200 bytes) / 3.5 chars per token
Output Tokens = (responseLength - 100 bytes) / 3.5 chars per token
```

## ✅ What You Need for Accurate Analysis

CSV format with ACTUAL token counts:
```csv
timestamp [UTC],input_tokens,output_tokens,total_tokens
"8/18/2025, 12:00:38.941 AM",1345,69,1414
"8/18/2025, 12:00:41.959 AM",967,48,1015
```

## 🎯 Get Real Token Data

**Best Option:** Log from your application
```python
# Every API call
response = client.chat.completions.create(...)
usage = response.usage
# Log: usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
```

See `GET_REAL_TOKEN_DATA.md` for complete guide.

## 🚀 Quick Start

1. ✅ Convert your current logs: `python3 convert_azure_logs.py sample/PT1H-2.json output.csv`
2. ✅ Upload to PTU Calculator app for initial analysis
3. ⚠️ Note: Results are estimates only
4. ✅ Implement application logging for real data
5. ✅ Re-run analysis with actual token counts
6. ✅ Make PTU decisions based on real data

## 📂 Files Created

- `convert_azure_logs.py` - Conversion script
- `README_AZURE_LOGS.md` - Azure logs overview
- `GET_REAL_TOKEN_DATA.md` - How to get accurate data
- `sample/PT1H-2_converted.csv` - Converted output (ESTIMATES)

## 💡 Pro Tips

1. **Add safety buffer:** If using estimates, multiply PTU needs by 1.3-1.5x
2. **Validate assumptions:** Compare estimated vs actual on sample data
3. **Monitor streaming:** Streaming responses may not be fully captured in logs
4. **Check all models:** Different models have different tokenization
5. **Peak vs average:** PTU sizing should handle peak TPM, not just average

## 🤔 When to Trust Estimates

| Scenario | Use Estimates? | Confidence |
|----------|---------------|------------|
| Initial feasibility study | ✅ Yes | Low |
| Budget planning | ⚠️ With 1.5x buffer | Medium |
| Proof of concept | ✅ Yes | Low |
| Production PTU purchase | ❌ No - Get real data | High |
| Annual commitment | ❌ No - Get real data | High |

---

**Bottom Line:** Use the converted logs for initial analysis, but collect real token data before making any PTU commitments.

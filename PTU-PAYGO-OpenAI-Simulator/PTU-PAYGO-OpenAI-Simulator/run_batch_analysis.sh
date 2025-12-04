#!/bin/bash

# Batch PTU Analysis Runner
# This script runs the PTU analysis for all major models

echo "======================================================================"
echo "PTU BATCH ANALYSIS"
echo "======================================================================"
echo ""
echo "This will analyze your Azure OpenAI usage data and generate"
echo "PTU sizing recommendations for each model/version."
echo ""
echo "Processing 67M requests from 4.5 GB CSV file..."
echo "This will take about 5-10 minutes."
echo ""
echo "Output will be saved to: batch_analysis_output/"
echo ""
echo "Starting analysis..."
echo ""

# Run the batch analysis
python3 batch_analyze_by_model_version.py \
  --top-n 10 \
  --min-requests 1000000 \
  --ptu-price 221.0 \
  --ptu-capacity 3000 \
  --min-ptus 15 \
  --max-ptus 100

echo ""
echo "======================================================================"
echo "Analysis complete! Check batch_analysis_output/ for results."
echo "======================================================================"

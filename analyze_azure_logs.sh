#!/bin/bash
#
# Quick start script for analyzing Azure OpenAI logs
#
# Usage:
#   ./analyze_azure_logs.sh
#
# This will prompt you for your Azure Storage connection string if not set

set -e

echo "=================================================="
echo "Azure OpenAI Logs Analyzer - Quick Start"
echo "=================================================="
echo ""

# Check if connection string is set
if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "⚠️  AZURE_STORAGE_CONNECTION_STRING not set"
    echo ""
    echo "Please provide your Azure Storage connection string:"
    echo "  1. Go to Azure Portal"
    echo "  2. Navigate to Storage Account: nvstrgitentint"
    echo "  3. Go to Security + networking → Access keys"
    echo "  4. Copy Connection string from key1 or key2"
    echo ""
    echo -n "Paste connection string here (or press Ctrl+C to exit): "
    read -r CONNECTION_STRING
    
    if [ -z "$CONNECTION_STRING" ]; then
        echo "❌ No connection string provided. Exiting."
        exit 1
    fi
    
    export AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING"
    echo "✅ Connection string set"
    echo ""
fi

# Check if azure-storage-blob is installed
echo "📦 Checking dependencies..."
python3 -c "import azure.storage.blob" 2>/dev/null || {
    echo "Installing azure-storage-blob..."
    pip3 install azure-storage-blob
}
echo "✅ Dependencies ready"
echo ""

# Run the analysis
echo "🚀 Starting analysis of storage account: nvstrgitentint"
echo "   Container: insights-logs-requestresponse"
echo ""

python3 download_azure_logs.py \
    --storage-account nvstrgitentint \
    --container insights-logs-requestresponse \
    --output azure_openai_complete_analysis.csv

echo ""
echo "=================================================="
echo "✅ Analysis Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Review: ./analysis_output/azure_openai_complete_analysis_report.txt"
echo "  2. Upload CSV to PTU Calculator: streamlit run app.py"
echo "  3. Remember: Token counts are estimates (±25-30%)"
echo ""

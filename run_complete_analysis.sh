#!/bin/bash
#
# Azure Storage Analysis - Azure AD Authentication
#
# This script will help you set up and run the complete analysis

set -e

echo "================================================================================"
echo "Azure OpenAI Logs Complete Analysis"
echo "================================================================================"
echo ""
echo "Storage Account: https://nvstrgitentint.blob.core.windows.net/"
echo "Container: standard"
echo "Authentication: Azure AD (DefaultAzureCredential)"
echo ""
echo "This will analyze ALL logs in your Azure Storage Account and generate:"
echo "  1. Complete CSV file for PTU Calculator"
echo "  2. Detailed analysis report with statistics"
echo ""
echo "================================================================================"
echo ""

# Check if Azure CLI is installed and user is logged in
echo "� Checking Azure authentication..."
echo ""

if ! command -v az &> /dev/null; then
    echo "⚠️  Azure CLI not found"
    echo ""
    echo "To install Azure CLI:"
    echo "  macOS: brew install azure-cli"
    echo "  Or visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    echo ""
    echo "After installing, run: az login"
    echo ""
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo "❌ Not logged in to Azure"
    echo ""
    echo "Please run: az login"
    echo ""
    echo "Then run this script again."
    exit 1
fi

ACCOUNT_NAME=$(az account show --query name -o tsv)
echo "✅ Logged in to Azure as: $ACCOUNT_NAME"
echo ""

echo ""
echo "================================================================================"
echo "📦 Checking Dependencies"
echo "================================================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.7+"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check/Install azure packages
echo "Checking Azure packages..."
python3 -c "import azure.storage.blob; import azure.identity" 2>/dev/null || {
    echo "Installing azure-storage-blob and azure-identity..."
    pip3 install azure-storage-blob azure-identity
}
echo "✅ Azure Storage SDK and Azure Identity ready"

echo ""
echo "================================================================================"
echo "🚀 Starting Complete Analysis"
echo "================================================================================"
echo ""
echo "This may take 10-30 minutes depending on log volume..."
echo "Progress will be shown as blobs are processed."
echo ""
echo "Press Ctrl+C to cancel at any time."
echo ""

# Run the analysis
python3 download_azure_logs.py \
    --account-url "https://nvstrgitentint.blob.core.windows.net/" \
    --container standard \
    --use-aad \
    --output nvstrgitentint_complete_analysis.csv

EXIT_CODE=$?

echo ""
echo "================================================================================"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ ANALYSIS COMPLETE!"
    echo "================================================================================"
    echo ""
    echo "📊 Generated Files:"
    echo "  CSV: ./analysis_output/nvstrgitentint_complete_analysis.csv"
    echo "  Report: ./analysis_output/nvstrgitentint_complete_analysis_report.txt"
    echo ""
    echo "📈 Next Steps:"
    echo "  1. Review the report:"
    echo "     cat ./analysis_output/nvstrgitentint_complete_analysis_report.txt"
    echo ""
    echo "  2. Upload CSV to PTU Calculator:"
    echo "     streamlit run app.py"
    echo "     Then upload: nvstrgitentint_complete_analysis.csv"
    echo ""
    echo "  ⚠️  Remember: Token counts are ESTIMATES (±25-30%)"
    echo "     Add 1.3-1.5x safety buffer to PTU calculations"
    echo ""
else
    echo "❌ ANALYSIS FAILED"
    echo "================================================================================"
    echo ""
    echo "Common issues:"
    echo "  - Invalid connection string"
    echo "  - No permissions on storage account"
    echo "  - Network connectivity issues"
    echo "  - Container doesn't exist or is empty"
    echo ""
    echo "Check the error message above for details."
    exit $EXIT_CODE
fi

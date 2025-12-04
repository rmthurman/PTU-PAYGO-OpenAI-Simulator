"""
Test script to verify Azure OpenAI usage extraction functionality.
"""

import os
import sys
from datetime import datetime, timedelta

def test_imports():
    """Test that all required packages are installed"""
    print("Testing imports...")
    try:
        import pandas
        import azure.storage.blob
        import azure.identity
        print("  ✓ All required packages installed")
        return True
    except ImportError as e:
        print(f"  ✗ Missing package: {e}")
        return False

def test_azure_connection():
    """Test Azure authentication"""
    print("\nTesting Azure authentication...")
    try:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
        # Try to get a token
        token = credential.get_token("https://storage.azure.com/.default")
        print("  ✓ Azure authentication successful")
        return True
    except Exception as e:
        print(f"  ✗ Azure authentication failed: {e}")
        print("  → Run 'az login' to authenticate")
        return False

def test_storage_access():
    """Test storage account access"""
    print("\nTesting storage account access...")
    try:
        from azure.storage.blob import BlobServiceClient
        from azure.identity import DefaultAzureCredential
        
        storage_account = "randyscommondatawus3"
        storage_url = f"https://{storage_account}.blob.core.windows.net"
        
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url=storage_url, credential=credential)
        
        # Try to list containers
        containers = list(blob_service_client.list_containers())
        print(f"  ✓ Storage account accessible ({len(containers)} containers found)")
        return True
    except Exception as e:
        print(f"  ✗ Storage access failed: {e}")
        print("  → Check permissions and network access")
        return False

def test_extraction_script():
    """Test the extraction script exists and is runnable"""
    print("\nTesting extraction script...")
    if not os.path.exists("extract_azure_usage.py"):
        print("  ✗ extract_azure_usage.py not found")
        return False
    
    print("  ✓ Extraction script found")
    return True

def test_sample_extraction():
    """Test a small data extraction"""
    print("\nTesting sample data extraction...")
    try:
        import subprocess
        
        # Try to list accounts (quick test)
        result = subprocess.run(
            [sys.executable, "extract_azure_usage.py", "--list-accounts"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("  ✓ Extraction script runs successfully")
            # Show account list
            for line in result.stdout.split('\n'):
                if '  -' in line:
                    print(f"    {line}")
            return True
        else:
            print(f"  ✗ Extraction failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ✗ Script timed out")
        return False
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

def test_simulator_components():
    """Test simulator components exist"""
    print("\nTesting simulator components...")
    required_files = [
        "app.py",
        "data_processing.py",
        "ptu_calculations.py",
        "pricing.py",
        "utils.py",
        "extract_azure_usage.py",
        "quick_extract.py"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} missing")
            all_exist = False
    
    return all_exist

def run_all_tests():
    """Run all tests"""
    print("="*70)
    print("PTU-PAYGO Simulator - System Test")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Package Imports", test_imports()))
    results.append(("Azure Authentication", test_azure_connection()))
    results.append(("Storage Access", test_storage_access()))
    results.append(("Extraction Script", test_extraction_script()))
    results.append(("Simulator Components", test_simulator_components()))
    results.append(("Sample Extraction", test_sample_extraction()))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Extract usage data: python extract_azure_usage.py --days 30")
        print("  2. Start simulator: streamlit run app.py")
        return True
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted.")
        sys.exit(1)

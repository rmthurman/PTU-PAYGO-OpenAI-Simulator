#!/usr/bin/env python3
"""
One-command script to extract Azure usage and start the simulator.
"""

import subprocess
import sys
import os
from datetime import datetime

def run_command(cmd, description):
    """Run a command and show progress"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}")
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"\n✗ Failed: {description}")
        return False
    
    print(f"\n✓ Success: {description}")
    return True

def main():
    print("="*70)
    print("Azure OpenAI PTU Analyzer - Quick Start")
    print("="*70)
    
    # Check if we need to extract data
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'usage' in f.lower()]
    
    if csv_files:
        print(f"\nFound {len(csv_files)} existing usage CSV file(s):")
        for f in csv_files:
            stat = os.stat(f)
            size_mb = stat.st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            print(f"  - {f} ({size_mb:.2f} MB, modified {mod_time.strftime('%Y-%m-%d %H:%M')})")
        
        response = input("\nExtract new data? (y/N): ").strip().lower()
        extract = response == 'y'
    else:
        print("\nNo existing usage CSV files found.")
        extract = True
    
    if extract:
        # Ask for days
        print("\nHow many days of data to extract?")
        print("  1. Last 7 days (quick)")
        print("  2. Last 30 days (recommended)")
        print("  3. Last 90 days (comprehensive)")
        print("  4. Custom date range")
        
        choice = input("\nSelect (1-4) [default: 2]: ").strip() or "2"
        
        if choice == "1":
            cmd = "python extract_azure_usage.py --days 7 --include-metadata"
        elif choice == "2":
            cmd = "python extract_azure_usage.py --days 30 --include-metadata"
        elif choice == "3":
            cmd = "python extract_azure_usage.py --days 90 --include-metadata"
        elif choice == "4":
            start = input("Start date (YYYY-MM-DD): ").strip()
            end = input("End date (YYYY-MM-DD): ").strip()
            cmd = f"python extract_azure_usage.py --start-date {start} --end-date {end} --include-metadata"
        else:
            print("Invalid choice, using default (30 days)")
            cmd = "python extract_azure_usage.py --days 30 --include-metadata"
        
        success = run_command(cmd, "Extracting Azure OpenAI usage data")
        
        if not success:
            print("\nData extraction failed. Please check:")
            print("  1. You're logged in: az login")
            print("  2. You have permissions: Storage Blob Data Reader")
            print("  3. Network access to storage account")
            sys.exit(1)
    
    # Start the simulator
    print("\n" + "="*70)
    print("Starting PTU vs PAYGO Simulator")
    print("="*70)
    print("\nThe simulator will open in your browser at http://localhost:8501")
    print("Press Ctrl+C to stop the simulator\n")
    
    try:
        subprocess.run("streamlit run app.py", shell=True)
    except KeyboardInterrupt:
        print("\n\nSimulator stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        sys.exit(1)

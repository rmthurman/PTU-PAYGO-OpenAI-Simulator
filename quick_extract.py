"""
Quick extraction helper script with common scenarios.
This provides shortcuts for the most common extraction tasks.
"""

import subprocess
import sys
from datetime import datetime, timedelta

def run_extraction(args):
    """Run the extraction script with given arguments"""
    cmd = [sys.executable, "extract_azure_usage.py"] + args
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode

def print_menu():
    """Display menu of common scenarios"""
    print("="*70)
    print("Azure OpenAI Usage Data - Quick Extraction")
    print("="*70)
    print("\nCommon Scenarios:")
    print("  1. Extract last 7 days (all accounts)")
    print("  2. Extract last 30 days (all accounts)")
    print("  3. Extract last 90 days (all accounts)")
    print("  4. Extract current month")
    print("  5. Extract previous month")
    print("  6. Extract specific date range")
    print("  7. List available accounts")
    print("  8. Extract by account (interactive)")
    print("  9. Exit")
    print()

def get_month_range(year, month):
    """Get first and last day of a month"""
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')

def extract_last_n_days(days):
    """Extract last N days"""
    output = f"usage_last_{days}days.csv"
    args = ["--days", str(days), "--output", output, "--include-metadata"]
    return run_extraction(args)

def extract_current_month():
    """Extract current month"""
    now = datetime.now()
    start_date = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    output = f"usage_{now.strftime('%Y_%m')}.csv"
    
    args = [
        "--start-date", start_date,
        "--end-date", end_date,
        "--output", output,
        "--include-metadata"
    ]
    return run_extraction(args)

def extract_previous_month():
    """Extract previous month"""
    now = datetime.now()
    if now.month == 1:
        prev_month = 12
        prev_year = now.year - 1
    else:
        prev_month = now.month - 1
        prev_year = now.year
    
    start_date, end_date = get_month_range(prev_year, prev_month)
    output = f"usage_{prev_year}_{prev_month:02d}.csv"
    
    args = [
        "--start-date", start_date,
        "--end-date", end_date,
        "--output", output,
        "--include-metadata"
    ]
    return run_extraction(args)

def extract_custom_range():
    """Extract custom date range"""
    print("\nEnter date range:")
    start_date = input("  Start date (YYYY-MM-DD): ").strip()
    end_date = input("  End date (YYYY-MM-DD): ").strip()
    output = input("  Output file name (default: custom_usage.csv): ").strip() or "custom_usage.csv"
    
    args = [
        "--start-date", start_date,
        "--end-date", end_date,
        "--output", output,
        "--include-metadata"
    ]
    return run_extraction(args)

def list_accounts():
    """List available accounts"""
    args = ["--list-accounts"]
    return run_extraction(args)

def extract_by_account():
    """Extract data for specific accounts"""
    print("\nAvailable accounts:")
    list_accounts()
    
    print("\nEnter account names (space-separated):")
    accounts = input("  Accounts: ").strip().split()
    
    days = input("  Number of days (default: 30): ").strip() or "30"
    output = input("  Output file name (default: account_usage.csv): ").strip() or "account_usage.csv"
    
    args = [
        "--days", days,
        "--accounts"] + accounts + [
        "--output", output,
        "--include-metadata"
    ]
    return run_extraction(args)

def main():
    """Main menu loop"""
    while True:
        print_menu()
        choice = input("Select option (1-9): ").strip()
        
        print()
        
        if choice == "1":
            extract_last_n_days(7)
        elif choice == "2":
            extract_last_n_days(30)
        elif choice == "3":
            extract_last_n_days(90)
        elif choice == "4":
            extract_current_month()
        elif choice == "5":
            extract_previous_month()
        elif choice == "6":
            extract_custom_range()
        elif choice == "7":
            list_accounts()
        elif choice == "8":
            extract_by_account()
        elif choice == "9":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please select 1-9.")
        
        print("\n" + "="*70 + "\n")
        input("Press Enter to continue...")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

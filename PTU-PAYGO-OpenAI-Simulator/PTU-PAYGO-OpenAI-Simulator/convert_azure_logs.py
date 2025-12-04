"""
Convert Azure OpenAI diagnostic logs (JSON) to PTU Calculator CSV format.

This script processes Azure diagnostic logs and extracts token usage information
into the format expected by the PTU Calculator app.

Input: JSON file with Azure diagnostic logs
Output: CSV with columns: timestamp [UTC], input_tokens, output_tokens, total_tokens
"""

import json
import csv
import sys
from datetime import datetime
from pathlib import Path


def parse_properties(properties_str):
    """Parse the properties JSON string to extract token information."""
    try:
        # The properties field is a JSON string, so we need to parse it
        props = json.loads(properties_str)
        return props
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_tokens_from_log(log_entry):
    """Extract token information from a single log entry.
    
    Returns:
        tuple: (timestamp, input_tokens, output_tokens, total_tokens) or None if invalid
    """
    # Only process successful ChatCompletions
    if log_entry.get('operationName') != 'ChatCompletions_Create':
        return None
    
    if log_entry.get('resultSignature') != '200':
        return None
    
    # Parse timestamp
    timestamp_str = log_entry.get('time')
    if not timestamp_str:
        return None
    
    try:
        # Parse ISO format timestamp: "2025-08-15T17:07:18.5530000Z"
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # Format as expected by PTU Calculator: "8/18/2025, 12:00:38.941 AM"
        formatted_time = dt.strftime("%-m/%-d/%Y, %-I:%M:%S.%f %p")
    except (ValueError, AttributeError):
        return None
    
    # Parse properties to get token information
    properties_str = log_entry.get('properties', '{}')
    props = parse_properties(properties_str)
    
    # Check if actual token counts are available in properties
    prompt_tokens = props.get('prompt_tokens') or props.get('promptTokens')
    completion_tokens = props.get('completion_tokens') or props.get('completionTokens')
    total_tokens_prop = props.get('total_tokens') or props.get('totalTokens')
    
    if prompt_tokens is not None and completion_tokens is not None:
        # We have actual token counts!
        input_tokens = int(prompt_tokens)
        output_tokens = int(completion_tokens)
        total_tokens = input_tokens + output_tokens
        return (formatted_time, input_tokens, output_tokens, total_tokens)
    
    # Fall back to estimation from request/response lengths
    request_length = props.get('requestLength', 0)
    response_length = props.get('responseLength', 0)
    
    if not request_length and not response_length:
        return None
    
    # Improved token estimation based on typical JSON overhead
    # Request includes: JSON structure, system prompts, user messages
    # Response includes: JSON structure, assistant message
    # Conservative estimate: ~3.5 characters per token for JSON-wrapped content
    CHARS_PER_TOKEN = 3.5
    
    # Estimate input tokens (request typically has more JSON overhead)
    # Subtract ~200 bytes for typical OpenAI API request structure
    estimated_content_length = max(0, request_length - 200)
    input_tokens = max(1, int(estimated_content_length / CHARS_PER_TOKEN)) if request_length else 0
    
    # Estimate output tokens (response has less overhead)
    # Subtract ~100 bytes for typical OpenAI API response structure
    estimated_response_content = max(0, response_length - 100)
    output_tokens = max(1, int(estimated_response_content / CHARS_PER_TOKEN)) if response_length else 0
    
    total_tokens = input_tokens + output_tokens
    
    if total_tokens == 0:
        return None
    
    return (formatted_time, input_tokens, output_tokens, total_tokens)


def convert_azure_logs_to_csv(input_json_path, output_csv_path):
    """Convert Azure diagnostic logs JSON to PTU Calculator CSV format.
    
    Args:
        input_json_path: Path to input JSON file (can be single object or array)
        output_csv_path: Path to output CSV file
    """
    print(f"Reading Azure logs from: {input_json_path}")
    
    with open(input_json_path, 'r') as f:
        content = f.read().strip()
    
    # Handle both single object and array of objects
    if content.startswith('['):
        # Array of log entries
        log_entries = json.loads(content)
    else:
        # Single log entry or newline-delimited JSON
        log_entries = []
        for line in content.split('\n'):
            line = line.strip()
            if line:
                try:
                    log_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    print(f"Found {len(log_entries)} log entries")
    
    # Extract token data
    rows = []
    skipped = 0
    
    for entry in log_entries:
        result = extract_tokens_from_log(entry)
        if result:
            rows.append(result)
        else:
            skipped += 1
    
    print(f"Extracted {len(rows)} valid token records (skipped {skipped} entries)")
    
    if not rows:
        print("ERROR: No valid token data found in logs")
        print("\n⚠️  Note: Azure diagnostic logs may not contain token counts.")
        print("Consider using Azure OpenAI usage logs or API response logs instead.")
        return False
    
    # Check if we're using estimates vs actual counts
    print("\n⚠️  DATA QUALITY WARNING:")
    print("These Azure logs contain requestLength/responseLength in bytes, NOT actual token counts.")
    print("Token values are ESTIMATES based on character-to-token ratio (~3.5 chars/token).")
    print("\nFor ACCURATE PTU planning, you need logs with actual token counts:")
    print("  - Properties should contain: prompt_tokens, completion_tokens, total_tokens")
    print("  - Or capture token usage from your application's API responses")
    
    # Sort by timestamp
    rows.sort(key=lambda x: x[0])
    
    # Write CSV
    print(f"Writing CSV to: {output_csv_path}")
    
    with open(output_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens'])
        writer.writerows(rows)
    
    print(f"✅ Successfully created CSV with {len(rows)} rows")
    
    # Show sample
    print("\nSample of first 3 rows:")
    for i, row in enumerate(rows[:3], 1):
        print(f"{i}. {row}")
    
    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python convert_azure_logs.py <input_json_file> [output_csv_file]")
        print("\nExample:")
        print("  python convert_azure_logs.py sample/PT1H.json sample/PT1H_converted.csv")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    # Default output path
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_suffix('.csv')
    
    success = convert_azure_logs_to_csv(input_path, output_path)
    
    if success:
        print(f"\n📊 You can now upload {output_path.name} to the PTU Calculator app!")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Data processing module for PTU Calculator.

Handles CSV file processing, column mapping, dataframe preparation,
and minute-level aggregation of token usage data.
"""

from typing import Tuple, Dict
import pandas as pd


EXPECTED_COLS = [
    "timestamp [utc]",
    "input tokens",
    "output tokens", 
    "total tokens",
]


def find_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Return a mapping from canonical names to actual dataframe column names.

    Canonical keys: 'timestamp', 'input', 'output', 'total'
    """
    cols = {c.lower(): c for c in df.columns}
    mapping = {}

    # timestamp column: prefer exact match, else any column containing 'timestamp'
    ts_candidates = [c for c_low, c in cols.items() if 'timestamp' in c_low]
    if ts_candidates:
        mapping['timestamp'] = ts_candidates[0]

    # token columns
    for target in ['input', 'output', 'total']:
        for c_low, c in cols.items():
            if target in c_low and 'token' in c_low:
                mapping[target] = c
                break

    return mapping


def prepare_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Parse and prepare the uploaded CSV data.
    
    Returns:
        Tuple of (processed_dataframe, error_message)
        If successful, error_message is empty string.
    """
    if df.empty:
        return df, "Empty dataframe"

    col_mapping = find_columns(df)
    
    missing = [k for k in ['timestamp', 'input', 'output'] if k not in col_mapping]
    if missing:
        available = list(df.columns)
        return df, f"Missing required columns: {missing}. Available columns: {available}"

    # Create a clean dataframe with standardized column names
    clean_df = pd.DataFrame()
    clean_df['timestamp'] = df[col_mapping['timestamp']]
    clean_df['input_tokens'] = pd.to_numeric(df[col_mapping['input']], errors='coerce')
    clean_df['output_tokens'] = pd.to_numeric(df[col_mapping['output']], errors='coerce')
    
    # Handle total tokens - use existing if available, otherwise calculate
    if 'total' in col_mapping:
        clean_df['total_tokens'] = pd.to_numeric(df[col_mapping['total']], errors='coerce')
    else:
        clean_df['total_tokens'] = clean_df['input_tokens'] + clean_df['output_tokens']

    # Drop rows with invalid data
    initial_rows = len(clean_df)
    clean_df = clean_df.dropna()
    final_rows = len(clean_df)
    
    if final_rows == 0:
        return clean_df, "No valid data rows after cleaning"
    
    # Parse timestamps (simplified approach like original app)
    import re
    
    def _normalize(ts_value):
        """Normalize timestamp format to ensure consistent parsing"""
        if pd.isna(ts_value):
            return ts_value
        s = str(ts_value).strip()
        # Handle format like "8/18/2025, 12:06:23.290 AM" - normalize month/day to 2 digits
        m = re.match(r"^(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}),\s*(?P<rest>.*)$", s)
        if m:
            mm = m.group('m').zfill(2)
            dd = m.group('d').zfill(2)
            yyyy = m.group('y')
            rest = m.group('rest')
            return f"{mm}/{dd}/{yyyy}, {rest}"
        return s

    ts_col = col_mapping['timestamp']
    clean_df['timestamp'] = df[ts_col].apply(_normalize)
    
    # Parse with expected format
    try:
        fmt = "%m/%d/%Y, %I:%M:%S.%f %p"
        clean_df['timestamp'] = pd.to_datetime(clean_df['timestamp'], format=fmt, utc=True, errors='raise')
    except Exception as e:
        # Fallback to general parser
        try:
            clean_df['timestamp'] = pd.to_datetime(clean_df['timestamp'], errors='coerce')
        except Exception:
            return clean_df, f"Failed to parse timestamps: {str(e)}"
    
    # Drop rows with invalid timestamps
    clean_df = clean_df.dropna(subset=['timestamp'])
    
    if len(clean_df) == 0:
        return clean_df, "No valid timestamps found"
    
    # Sort by timestamp
    clean_df = clean_df.sort_values('timestamp').reset_index(drop=True)
    
    # Create minute column for aggregation
    clean_df['minute'] = clean_df['timestamp'].dt.floor('T')
    
    info = f"Processed {final_rows} rows"
    if initial_rows != final_rows:
        info += f" (dropped {initial_rows - final_rows} invalid rows)"
    
    return clean_df, ""


def compute_minute_aggregation(minutes_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate token usage by minute.
    
    Args:
        minutes_df: DataFrame with columns ['minute', 'input_tokens', 'output_tokens', 'total_tokens']
        
    Returns:
        DataFrame with minute-level aggregations
    """
    if minutes_df.empty:
        return pd.DataFrame()
    
    # Group by minute and sum the tokens
    minute_agg = minutes_df.groupby('minute').agg({
        'input_tokens': 'sum',
        'output_tokens': 'sum', 
        'total_tokens': 'sum'
    })
    # Build complete minute index from first to last
    full_index = pd.date_range(minute_agg.index.min(), minute_agg.index.max(), freq='T')
    minute_agg = minute_agg.reindex(full_index, fill_value=0)
    minute_agg = minute_agg.reset_index().rename(columns={'index': 'minute'})
    # Add tokens_per_minute column for backward compatibility (like original app)
    minute_agg['tokens_per_minute'] = minute_agg['total_tokens']
    # Add date column
    minute_agg['date'] = minute_agg['minute'].dt.date
    
    return minute_agg


def compute_stats_per_date(minute_series: pd.DataFrame) -> pd.DataFrame:
    """Compute daily statistics from minute-level data.
    
    Args:
        minute_series: DataFrame with minute-level token data
        
    Returns:
        DataFrame with daily statistics
    """
    if minute_series.empty:
        return pd.DataFrame()
    
    # Extract date from minute timestamp
    minute_series['date'] = minute_series['minute'].dt.date
    
    # Group by date and compute statistics
    daily_stats = minute_series.groupby('date')['total_tokens'].agg([
        ('max_tpm', 'max'),
        ('min_tpm', 'min'), 
        ('median_tpm', 'median'),
        ('mean_tpm', 'mean')
    ]).reset_index()
    
    return daily_stats
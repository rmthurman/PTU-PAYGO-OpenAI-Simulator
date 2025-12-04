"""
Utility functions for the PTU Calculator.

Contains helper functions for file downloads, data formatting,
and other common operations.
"""

import base64
import pandas as pd
from typing import List, Any


def create_download_link(df: pd.DataFrame, file_name: str, label: str) -> str:
    """Create a download link for a pandas DataFrame as CSV.
    
    Args:
        df: DataFrame to download
        file_name: Name for the downloaded file
        label: Text to display for the download link
        
    Returns:
        HTML string for the download link
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{file_name}">{label}</a>'
    return href


def chunks(lst: List[Any], n: int) -> List[List[Any]]:
    """Split a list into chunks of size n.
    
    Args:
        lst: List to split
        n: Size of each chunk
        
    Returns:
        List of chunks
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def format_large_number(num: float) -> str:
    """Format large numbers with appropriate suffixes (K, M, B).
    
    Args:
        num: Number to format
        
    Returns:
        Formatted string
    """
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return f"{num:,.0f}"


def get_dataset_duration_days(df: pd.DataFrame, timestamp_col: str = 'timestamp') -> float:
    """Calculate the duration of the dataset in days.
    
    Args:
        df: DataFrame with timestamp column
        timestamp_col: Name of the timestamp column
        
    Returns:
        Duration in days (as float)
    """
    if df.empty or timestamp_col not in df.columns:
        return 0.0
    
    timestamps = pd.to_datetime(df[timestamp_col])
    duration = (timestamps.max() - timestamps.min()).total_seconds()
    return duration / 86400.0  # Convert seconds to days